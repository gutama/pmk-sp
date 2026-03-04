"""FastAPI server for FMI SimEngine — REST API + WebSocket."""
from __future__ import annotations
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import socketio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    SimulationRequest,
    SimulationStatus,
    HeatmapResponse,
    HeatmapRowData,
    HeatmapCellData,
    TimeSeriesResponse,
    TimeSeriesPoint,
    NetworkResponse,
    ContagionResponse,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
)

# In-memory simulation store (replace with DuckDB for production)
_simulations: dict[str, dict[str, Any]] = {}
_results: dict[str, Any] = {}


def create_app(config_dir: str | Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="FMI-SimEngine API",
        description="FMI Simulation Engine for Bank Indonesia Payment System Risk Monitoring",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Socket.IO for real-time updates
    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
    socket_app = socketio.ASGIApp(sio, app)

    @sio.event
    async def connect(sid, environ):
        print(f"Client connected: {sid}")

    @sio.event
    async def disconnect(sid):
        print(f"Client disconnected: {sid}")

    @sio.event
    async def sim_pause(sid, data):
        sim_id = data.get("simulation_id")
        if sim_id in _simulations:
            _simulations[sim_id]["paused"] = True

    @sio.event
    async def sim_resume(sid, data):
        sim_id = data.get("simulation_id")
        if sim_id in _simulations:
            _simulations[sim_id]["paused"] = False

    @sio.event
    async def sim_abort(sid, data):
        sim_id = data.get("simulation_id")
        if sim_id in _simulations:
            _simulations[sim_id]["aborted"] = True

    # --- REST Endpoints ---

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/scenarios")
    async def list_scenarios():
        from ..scenarios.controller import ScenarioController
        ctrl = ScenarioController(config_dir)
        return {"scenarios": ctrl.list_scenarios()}

    @app.post("/api/simulate", response_model=SimulationStatus)
    async def start_simulation(
        request: SimulationRequest,
        background_tasks: BackgroundTasks,
    ):
        sim_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        _simulations[sim_id] = {
            "id": sim_id,
            "status": "pending",
            "progress_pct": 0.0,
            "current_day": 0,
            "total_days": request.n_days,
            "started_at": now,
            "config": request.model_dump(),
            "paused": False,
            "aborted": False,
        }
        background_tasks.add_task(_run_simulation, sim_id, request, sio)
        return SimulationStatus(
            simulation_id=sim_id,
            status="pending",
            total_days=request.n_days,
            started_at=now,
        )

    @app.get("/api/simulate/{simulation_id}", response_model=SimulationStatus)
    async def get_simulation_status(simulation_id: str):
        sim = _simulations.get(simulation_id)
        if not sim:
            raise HTTPException(404, f"Simulation {simulation_id} not found")
        return SimulationStatus(
            simulation_id=simulation_id,
            status=sim["status"],
            progress_pct=sim.get("progress_pct", 0.0),
            current_day=sim.get("current_day", 0),
            total_days=sim.get("total_days", 0),
            started_at=sim.get("started_at"),
            completed_at=sim.get("completed_at"),
            error_message=sim.get("error_message"),
        )

    @app.get("/api/results/{simulation_id}/heatmap", response_model=HeatmapResponse)
    async def get_heatmap(simulation_id: str, version: str = "nb"):
        sim = _get_completed_sim(simulation_id)
        result = _results.get(simulation_id)
        if not result:
            raise HTTPException(404, "Results not available yet")
        return _build_heatmap_response(simulation_id, result, version)

    @app.get("/api/results/{simulation_id}/timeseries", response_model=TimeSeriesResponse)
    async def get_timeseries(simulation_id: str, indicator: str = "tor"):
        _get_completed_sim(simulation_id)
        result = _results.get(simulation_id)
        if not result:
            raise HTTPException(404, "Results not available yet")
        return _build_timeseries_response(simulation_id, result, indicator)

    @app.get("/api/results/{simulation_id}/network", response_model=NetworkResponse)
    async def get_network(simulation_id: str, period: str = "latest", system: str = "rtgs"):
        _get_completed_sim(simulation_id)
        result = _results.get(simulation_id)
        if not result:
            raise HTTPException(404, "Results not available yet")
        return _build_network_response(simulation_id, result, period, system)

    @app.get("/api/results/{simulation_id}/contagion", response_model=ContagionResponse)
    async def get_contagion(simulation_id: str, bank_id: str | None = None):
        _get_completed_sim(simulation_id)
        result = _results.get(simulation_id)
        if not result:
            raise HTTPException(404, "Results not available yet")
        return _build_contagion_response(simulation_id, result, bank_id)

    @app.post("/api/compare", response_model=ScenarioCompareResponse)
    async def compare_scenarios(request: ScenarioCompareRequest):
        results_list = []
        for sim_id in request.simulation_ids:
            sim = _simulations.get(sim_id)
            if not sim:
                raise HTTPException(404, f"Simulation {sim_id} not found")
            results_list.append({
                "id": sim_id,
                "scenario": sim["config"].get("scenario", "unknown"),
                "result": _results.get(sim_id),
            })
        return _build_comparison_response(results_list)

    return socket_app


def _get_completed_sim(simulation_id: str) -> dict:
    sim = _simulations.get(simulation_id)
    if not sim:
        raise HTTPException(404, f"Simulation {simulation_id} not found")
    if sim["status"] not in ("completed", "failed"):
        raise HTTPException(409, f"Simulation {simulation_id} is still {sim['status']}")
    return sim


async def _run_simulation(
    sim_id: str, request: SimulationRequest, sio: socketio.AsyncServer
) -> None:
    """Background task: run simulation and emit progress via WebSocket."""
    sim = _simulations[sim_id]
    sim["status"] = "running"

    try:
        # Import here to avoid circular imports at module load
        from ..core.simulation import SimulationRunner

        runner = SimulationRunner(
            n_banks=request.n_banks,
            systems=request.systems,
            seed=request.seed,
        )

        # Progress callback
        async def on_day_complete(day: int, metrics: dict):
            sim["current_day"] = day
            sim["progress_pct"] = (day / request.n_days) * 100
            await sio.emit("sim:day_complete", {
                "simulation_id": sim_id,
                "day": day,
                "indicators": metrics,
                "network_snapshot": metrics.get("network_snapshot", {}),
            })

        result = runner.run(
            n_days=request.n_days,
            tick_interval_min=request.tick_interval_min,
            scenario=request.scenario,
            scenario_params=request.scenario_params,
        )

        _results[sim_id] = result
        sim["status"] = "completed"
        sim["progress_pct"] = 100.0
        sim["completed_at"] = datetime.now(timezone.utc).isoformat()

        await sio.emit("sim:complete", {
            "simulation_id": sim_id,
            "duration_seconds": result.duration_seconds if hasattr(result, "duration_seconds") else 0,
        })

    except Exception as exc:
        sim["status"] = "failed"
        sim["error_message"] = str(exc)
        sim["completed_at"] = datetime.now(timezone.utc).isoformat()
        await sio.emit("sim:error", {
            "simulation_id": sim_id,
            "message": str(exc),
            "recoverable": False,
        })
        raise


def _build_heatmap_response(
    sim_id: str, result: Any, version: str
) -> HeatmapResponse:
    """Convert SimulationResult into HeatmapResponse."""
    from ..indicators.thresholds import DEFAULT_THRESHOLDS

    periods = getattr(result, "periods", ["2025M1"])
    heatmap_data = getattr(result, "heatmap_data", {})
    version_data = heatmap_data.get(version, {})

    rows: list[HeatmapRowData] = []
    for indicator, values in version_data.items():
        t = DEFAULT_THRESHOLDS.get(indicator)
        row = HeatmapRowData(
            indicator=indicator,
            label=indicator.replace("_", " ").title(),
            pillar=_get_pillar(indicator),
            threshold_waspada=t.waspada if t else None,
            threshold_siaga=t.siaga if t else None,
            threshold_krisis=t.krisis if t else None,
            direction=t.direction if t else "inc",
            periods={
                period: HeatmapCellData(
                    value=val,
                    risk_zone=_classify_value(indicator, val, t),
                    formatted_value=_format_value(indicator, val),
                )
                for period, val in zip(periods, values)
            },
        )
        rows.append(row)

    return HeatmapResponse(
        version=version,
        simulation_id=sim_id,
        periods=periods,
        rows=rows,
        overall_risk_zone=_compute_overall_zone([r for row in rows for r in row.periods.values()]),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_timeseries_response(
    sim_id: str, result: Any, indicator: str
) -> TimeSeriesResponse:
    from ..indicators.thresholds import DEFAULT_THRESHOLDS
    from ..scenarios.calibration import HistoricalCalibrator

    periods = getattr(result, "periods", [])
    ts_data = getattr(result, "timeseries", {})
    values = ts_data.get(indicator, [])

    t = DEFAULT_THRESHOLDS.get(indicator)
    simulated = [
        TimeSeriesPoint(
            period=p,
            value=v,
            risk_zone=_classify_value(indicator, v, t),
        )
        for p, v in zip(periods, values)
    ]

    calibrator = HistoricalCalibrator()
    hist_series = calibrator.get_historical_series(indicator)
    historical = [
        TimeSeriesPoint(period=p, value=float(v), risk_zone=_classify_value(indicator, float(v), t))
        for p, v in zip(calibrator.HISTORICAL_DATA.get("periods", []), hist_series)
    ]

    thresholds = {}
    if t:
        thresholds = {"waspada": t.waspada, "siaga": t.siaga, "krisis": t.krisis}

    import numpy as np
    vals = [v for v in values if v is not None]
    stats = {}
    if vals:
        stats = {
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals)),
            "min": float(np.min(vals)),
            "max": float(np.max(vals)),
        }

    return TimeSeriesResponse(
        simulation_id=sim_id,
        indicator=indicator,
        simulated=simulated,
        historical=historical,
        thresholds=thresholds,
        direction=t.direction if t else "inc",
        statistics=stats,
    )


def _build_network_response(
    sim_id: str, result: Any, period: str, system: str
) -> NetworkResponse:
    import numpy as np
    network_data = getattr(result, "network_snapshots", {})
    snapshot = network_data.get(period, network_data.get("latest", {}))

    nodes_data = snapshot.get("nodes", [])
    edges_data = snapshot.get("edges", [])

    from .models import NetworkNode, NetworkEdge
    nodes = [NetworkNode(**n) for n in nodes_data] if nodes_data else []
    edges = [NetworkEdge(**e) for e in edges_data] if edges_data else []

    metrics = snapshot.get("metrics", {})
    return NetworkResponse(
        simulation_id=sim_id,
        period=period,
        system=system,
        nodes=nodes,
        edges=edges,
        metrics=metrics,
    )


def _build_contagion_response(
    sim_id: str, result: Any, bank_id: str | None
) -> ContagionResponse:
    contagion = getattr(result, "contagion_results", None)
    if not contagion:
        return ContagionResponse(
            simulation_id=sim_id,
            initial_bank=bank_id or "N/A",
            total_rounds=0,
            rounds=[],
            final_debtrank=0.0,
            total_banks_affected=0,
        )

    from .models import ContagionRound
    rounds = [
        ContagionRound(
            round_num=r["round"],
            shocked_banks=r.get("shocked", []),
            affected_banks=r.get("affected", []),
            cumulative_loss_pct=r.get("loss_pct", 0.0),
            debtrank_score=r.get("debtrank", 0.0),
        )
        for r in contagion.get("rounds", [])
    ]

    return ContagionResponse(
        simulation_id=sim_id,
        initial_bank=bank_id or contagion.get("initial_bank", ""),
        total_rounds=len(rounds),
        rounds=rounds,
        final_debtrank=contagion.get("final_debtrank", 0.0),
        total_banks_affected=contagion.get("total_affected", 0),
        systemic_importance=contagion.get("systemic_importance", {}),
    )


def _build_comparison_response(results: list[dict]) -> ScenarioCompareResponse:
    indicator_comparison = {}
    for r in results:
        sim_result = r.get("result")
        if not sim_result:
            continue
        heatmap = getattr(sim_result, "heatmap_data", {}).get("nb", {})
        for indicator, values in heatmap.items():
            if indicator not in indicator_comparison:
                indicator_comparison[indicator] = {}
            import numpy as np
            vals = [v for v in values if v is not None]
            indicator_comparison[indicator][r["id"]] = {
                "mean": float(np.mean(vals)) if vals else 0.0,
                "scenario": r["scenario"],
            }
    return ScenarioCompareResponse(
        simulations=[{"id": r["id"], "scenario": r["scenario"]} for r in results],
        indicator_comparison=indicator_comparison,
    )


def _get_pillar(indicator: str) -> str:
    velositas = {"tor", "tor_adj", "queue_ratio", "throughput_zona3"}
    struktur = {"awd", "avg_koneksi", "volatility_interconnectedness", "average_degree"}
    infrastruktur = {"incidents", "system_utilization", "system_availability"}
    if indicator in velositas:
        return "velositas"
    if indicator in struktur:
        return "struktur"
    if indicator in infrastruktur:
        return "infrastruktur"
    return "risiko"


def _classify_value(indicator: str, value: float | None, threshold: Any) -> str:
    if value is None or threshold is None:
        return "normal"
    try:
        from ..indicators.thresholds import ThresholdClassifier
        return ThresholdClassifier._classify(threshold, value)
    except Exception:
        return "normal"


def _format_value(indicator: str, value: float | None) -> str:
    if value is None:
        return "TBU"
    pct_indicators = {"system_availability", "throughput_zona3", "system_utilization",
                      "stability_index_provider_fast", "stability_index_participant_fast",
                      "availability_rtgs"}
    int_indicators = {"unsettled_banks", "avg_koneksi", "volatility_interconnectedness",
                      "unsettled_rtgs_dana", "reject_fast_dana", "unsettled_rtgs_nondana"}
    if indicator in pct_indicators:
        return f"{value:.2f}%"
    if indicator in int_indicators:
        return f"{int(value):,}"
    return f"{value:.2f}"


def _compute_overall_zone(cells: list[HeatmapCellData]) -> str:
    zone_order = {"normal": 0, "waspada": 1, "siaga": 2, "krisis": 3}
    max_zone = "normal"
    for cell in cells:
        if zone_order.get(cell.risk_zone, 0) > zone_order.get(max_zone, 0):
            max_zone = cell.risk_zone
    return max_zone
