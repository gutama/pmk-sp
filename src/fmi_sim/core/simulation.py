"""Main simulation orchestrator for FMI-SimEngine."""
from __future__ import annotations

import time
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from .agents import BankAgent, BankParams, MarketState, Payment, StressEvent
from .liquidity import LiquidityManager
from .network import NetworkParams, PaymentNetwork
from .settlement import SettlementConfig, SettlementEngine, TickResult


# ---------------------------------------------------------------------------
# System sizing defaults
# ---------------------------------------------------------------------------

_SYSTEM_SIZING: dict[str, dict[str, Any]] = {
    "rtgs": {
        "n_banks": 140,
        "core_fraction": 0.13,
        "core_liquidity": 8_000.0,
        "periphery_liquidity": 600.0,
        "core_credit": 4_000.0,
        "periphery_credit": 300.0,
        "core_pay_freq": 20.0,
        "periphery_pay_freq": 4.0,
        "core_pay_size": 300.0,
        "periphery_pay_size": 40.0,
        "operating_start_min": 480,
        "operating_end_min": 990,
        "zona1_cutoff_min": 660,
        "zona2_cutoff_min": 840,
    },
    "fast": {
        "n_banks": 80,
        "core_fraction": 0.15,
        "core_liquidity": 3_000.0,
        "periphery_liquidity": 200.0,
        "core_credit": 1_500.0,
        "periphery_credit": 100.0,
        "core_pay_freq": 25.0,
        "periphery_pay_freq": 5.0,
        "core_pay_size": 50.0,
        "periphery_pay_size": 10.0,
        "operating_start_min": 420,
        "operating_end_min": 1380,
        "zona1_cutoff_min": 600,
        "zona2_cutoff_min": 900,
    },
    "raja": {
        "n_banks": 70,
        "core_fraction": 0.14,
        "core_liquidity": 10_000.0,
        "periphery_liquidity": 1_000.0,
        "core_credit": 5_000.0,
        "periphery_credit": 500.0,
        "core_pay_freq": 10.0,
        "periphery_pay_freq": 2.0,
        "core_pay_size": 500.0,
        "periphery_pay_size": 80.0,
        "operating_start_min": 480,
        "operating_end_min": 990,
        "zona1_cutoff_min": 660,
        "zona2_cutoff_min": 840,
    },
}


# ---------------------------------------------------------------------------
# Historical calibration targets for synthetic series
# ---------------------------------------------------------------------------

_CALIB: dict[str, dict[str, float]] = {
    "tor":                  {"mean": 1.70, "std": 0.40},
    "average_degree":       {"mean": 73.5, "std": 1.5},
    "awd":                  {"mean": 2.60, "std": 0.30},
    "avg_koneksi":          {"mean": 4620.0, "std": 60.0},
    "vol_ic":               {"mean": 188.0, "std": 35.0},
    "system_utilization":   {"mean": 24.0, "std": 1.2},
    "qr":                   {"mean": 4.70, "std": 0.60},
    "throughput_zona3":     {"mean": 27.5, "std": 1.5},
}

# Scenario modifiers (additive mean-shifts relative to baseline)
_SCENARIO_SHIFTS: dict[str, dict[str, float]] = {
    "baseline": {},
    "liquidity_squeeze": {
        "tor": 0.8,
        "qr": 1.5,
        "throughput_zona3": 5.0,
        "awd": -0.3,
    },
    "counterparty_withdrawal": {
        "average_degree": -4.0,
        "avg_koneksi": -200.0,
        "vol_ic": 50.0,
    },
    "infrastructure_disruption": {
        "system_utilization": 3.0,
        "throughput_zona3": 8.0,
        "qr": 2.0,
    },
    "contagion_cascade": {
        "tor": 1.2,
        "average_degree": -6.0,
        "qr": 3.0,
        "throughput_zona3": 10.0,
    },
    "cyber_incident": {
        "average_degree": -2.0,
        "qr": 2.5,
        "system_utilization": 2.0,
    },
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SimulationResult:
    """Complete output from a simulation run.

    Attributes:
        simulation_id:      Unique identifier for this run.
        scenario:           Name of the scenario applied.
        n_banks:            Number of banks per system.
        n_days:             Number of simulated days.
        periods:            Monthly period labels (e.g. ['2025M1', ...]).
        heatmap_data:       Nested dict with keys 'nb' and 'pmkt', each
                            mapping indicator name -> list[float] (one per period).
        timeseries:         Daily time-series: indicator -> list[float].
        network_snapshots:  Per-period network snapshots (nodes/edges/metrics).
        contagion_results:  DebtRank contagion analysis results.
        daily_metrics:      Per-day aggregated metric dicts.
        duration_seconds:   Wall-clock time of the simulation run.
        seed:               Random seed used.
    """

    simulation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scenario: str = "baseline"
    n_banks: int = 140
    n_days: int = 30
    periods: list[str] = field(default_factory=list)
    heatmap_data: dict[str, dict[str, list[float]]] = field(
        default_factory=lambda: {"nb": {}, "pmkt": {}}
    )
    timeseries: dict[str, list[float]] = field(default_factory=dict)
    network_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    contagion_results: dict[str, Any] = field(default_factory=dict)
    daily_metrics: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    seed: int = 42


# ---------------------------------------------------------------------------
# SimulationRunner
# ---------------------------------------------------------------------------


class SimulationRunner:
    """Orchestrates a complete FMI simulation run.

    Parameters
    ----------
    n_banks:
        Number of bank agents to create for the RTGS system.
    systems:
        List of payment system identifiers to simulate.
    seed:
        Master random seed for full reproducibility.
    config_dir:
        Optional directory containing YAML configuration files.
    """

    _CORE_FRACTION: float = 0.13

    def __init__(
        self,
        n_banks: int = 140,
        systems: list[str] | None = None,
        seed: int = 42,
        config_dir: str | Path | None = None,
    ) -> None:
        self.n_banks = n_banks
        self.systems: list[str] = [s.lower() for s in (systems or ["rtgs", "fast", "raja"])]
        self.seed = seed
        self.config_dir = Path(config_dir) if config_dir else None

        self._rng = np.random.default_rng(seed)
        random.seed(seed)

        self._networks: dict[str, Any] = {}
        self._agents: dict[str, dict[int, BankAgent]] = {}
        self._engines: dict[str, SettlementEngine] = {}
        self._lm: LiquidityManager = LiquidityManager()

        self._config: dict[str, Any] = self._load_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        n_days: int = 30,
        tick_interval_min: int = 1,
        scenario: str = "baseline",
        scenario_params: dict[str, Any] | None = None,
        progress_callback: Callable | None = None,
    ) -> SimulationResult:
        """Execute the simulation.

        Parameters
        ----------
        n_days:
            Number of trading days to simulate.
        tick_interval_min:
            Duration of each simulation tick in minutes.
        scenario:
            Scenario name.
        scenario_params:
            Optional overrides for scenario parameters.
        progress_callback:
            Optional callable invoked after each day with
            (day_index, total_days, day_metrics).

        Returns
        -------
        SimulationResult
        """
        t_wall_start = time.perf_counter()
        sp = scenario_params or {}
        sim_id = str(uuid.uuid4())

        scenario_modifiers = _SCENARIO_SHIFTS.get(scenario, {})
        stress_events = self._build_stress_events_from_scenario(scenario, sp, n_days)

        for sys_name in self.systems:
            network = self._init_network(sys_name)
            self._networks[sys_name] = network
            agents = self._init_agents(network, sys_name)
            self._agents[sys_name] = agents
            engine = self._init_engines(network, agents, sys_name, tick_interval_min)
            self._engines[sys_name] = engine

        daily_results: list[dict[str, Any]] = []

        for day in range(1, n_days + 1):
            day_metrics = self._simulate_day(
                day=day,
                agents=self._agents,
                engines=self._engines,
                stress_events=stress_events,
                scenario_modifiers=scenario_modifiers,
                tick_interval_min=tick_interval_min,
            )
            daily_results.append(day_metrics)

            if progress_callback is not None:
                try:
                    progress_callback(day, n_days, day_metrics)
                except Exception:
                    pass

        heatmap_data = self._compute_heatmap(daily_results)
        periods = self._generate_periods(n_days)
        timeseries = self._generate_synthetic_series(n_days, scenario)
        timeseries = self._merge_daily_into_series(timeseries, daily_results, n_days)
        network_snapshots = self._build_network_snapshots()
        contagion_results = self._run_contagion_analysis()
        duration = time.perf_counter() - t_wall_start

        return SimulationResult(
            simulation_id=sim_id,
            scenario=scenario,
            n_banks=self.n_banks,
            n_days=n_days,
            periods=periods,
            heatmap_data=heatmap_data,
            timeseries=timeseries,
            network_snapshots=network_snapshots,
            contagion_results=contagion_results,
            daily_metrics=daily_results,
            duration_seconds=duration,
            seed=self.seed,
        )

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_network(self, system: str) -> Any:
        """Create a PaymentNetwork graph for the given system."""
        sizing = _SYSTEM_SIZING.get(system, _SYSTEM_SIZING["rtgs"])
        n_banks = sizing.get("n_banks", self.n_banks)
        if system == "rtgs":
            n_banks = self.n_banks

        sys_seed = int(self._rng.integers(0, 2**31))
        pn = PaymentNetwork(n_banks=n_banks, network_type=system)
        params = pn._build_default_params()
        params.seed = sys_seed
        return pn.generate_topology(params)

    def _init_agents(self, network: Any, system: str) -> dict[int, BankAgent]:
        """Create BankAgent instances for every node in network."""
        sizing = _SYSTEM_SIZING.get(system, _SYSTEM_SIZING["rtgs"])
        agents: dict[int, BankAgent] = {}

        for node_id in network.nodes():
            bank_type = network.nodes[node_id].get("bank_type", "periphery")
            agent_seed = int(self._rng.integers(0, 2**31))

            if bank_type == "core":
                liq = sizing["core_liquidity"]
                credit = sizing["core_credit"]
                pay_freq = sizing["core_pay_freq"]
                pay_size = sizing["core_pay_size"]
            else:
                liq = sizing["periphery_liquidity"]
                credit = sizing["periphery_credit"]
                pay_freq = sizing["periphery_pay_freq"]
                pay_size = sizing["periphery_pay_size"]

            bp = BankParams(
                bank_id=int(node_id),
                bank_type=bank_type,
                initial_liquidity=liq,
                credit_limit=credit,
                payment_frequency=pay_freq,
                avg_payment_size=pay_size,
                payment_size_std=pay_size * 0.40,
                urgency_dist=(0.10, 0.75, 0.15),
                risk_appetite=0.5,
                stress_sensitivity=0.5,
                seed=agent_seed,
            )
            agents[int(node_id)] = BankAgent(params=bp, system=system)

        return agents

    def _init_engines(
        self,
        network: Any,
        agents: dict[int, BankAgent],
        system: str,
        tick_interval_min: int = 1,
    ) -> SettlementEngine:
        """Create a SettlementEngine for the given system."""
        sizing = _SYSTEM_SIZING.get(system, _SYSTEM_SIZING["rtgs"])

        config = SettlementConfig(
            mode=system,
            gridlock_check_interval=max(1, 30 // max(1, tick_interval_min)),
            max_queue_size=10_000,
            operating_start_min=int(sizing.get("operating_start_min", 480)),
            operating_end_min=int(sizing.get("operating_end_min", 990)),
            zona1_cutoff_min=int(sizing.get("zona1_cutoff_min", 660)),
            zona2_cutoff_min=int(sizing.get("zona2_cutoff_min", 840)),
        )

        bank_balances: dict[str, float] = {
            str(bid): agent.params.initial_liquidity
            for bid, agent in agents.items()
        }

        return SettlementEngine(config=config, bank_balances=bank_balances)

    # ------------------------------------------------------------------
    # Per-day simulation
    # ------------------------------------------------------------------

    def _simulate_day(
        self,
        day: int,
        agents: dict[str, dict[int, BankAgent]],
        engines: dict[str, SettlementEngine],
        stress_events: list[Any],
        scenario_modifiers: dict[str, float],
        tick_interval_min: int = 1,
    ) -> dict[str, Any]:
        """Simulate one full trading day across all payment systems."""
        day_data: dict[str, Any] = {"day": day, "systems": {}}

        active_stress = [
            se for se in stress_events
            if hasattr(se, "is_active") and se.is_active(day)
        ]

        for sys_name in self.systems:
            sys_agents = agents[sys_name]
            engine = engines[sys_name]
            sizing = _SYSTEM_SIZING.get(sys_name, _SYSTEM_SIZING["rtgs"])
            network = self._networks[sys_name]

            engine.reset_day()
            for agent in sys_agents.values():
                agent.reset_daily_counters()
                self._restore_eod_liquidity(agent, engine, sys_name)

            for se in active_stress:
                _apply_scenario_stress_event(se, sys_agents, sys_name)

            operating_start = sizing.get("operating_start_min", 480)
            operating_end = sizing.get("operating_end_min", 990)
            trading_minutes = operating_end - operating_start
            ticks_per_day = max(1, trading_minutes // tick_interval_min)

            opening_balances: dict[str, float] = {
                str(bid): agent.liquidity for bid, agent in sys_agents.items()
            }

            tick_results: list[TickResult] = []

            for tick_idx in range(ticks_per_day):
                t_rel = tick_idx * tick_interval_min

                market_state = self._build_market_state(
                    sys_name, float(t_rel), active_stress, tick_results
                )

                counterparties = list(sys_agents.keys())
                all_payments: list[Payment] = []
                for agent in sys_agents.values():
                    pmts = agent.generate_payments(
                        t=float(t_rel),
                        market_state=market_state,
                        counterparties=counterparties,
                    )
                    all_payments.extend(pmts)

                tick_result = engine.process_tick(
                    tick=t_rel,
                    day=day,
                    payments=all_payments,
                    network=network,
                )
                tick_results.append(tick_result)

            daily_stats = engine.get_daily_stats()
            closing_balances: dict[str, float] = daily_stats["bank_balances"]

            bank_tor_data: dict[str, dict[str, Any]] = {
                str(bid): {
                    "settled_value": agent._daily_generated,
                    "opening_balance": opening_balances.get(str(bid), agent.params.initial_liquidity),
                    "closing_balance": closing_balances.get(str(bid), agent.liquidity),
                }
                for bid, agent in sys_agents.items()
            }
            system_tor = self._lm.compute_system_tor(bank_tor_data)

            net_stats = PaymentNetwork.get_network_stats(network)
            total_value = daily_stats["value_settled"]
            zona3_val = daily_stats["zona3_value"]
            submitted = daily_stats["submitted_value"]
            queued_val = sum(
                p.amount for q in engine._queues.values() for p in q.pending
            )

            throughput_z3 = self._lm.compute_throughput_zona3(zona3_val, total_value)
            queue_ratio = self._lm.compute_queue_ratio(queued_val, submitted)
            avg_degree = net_stats.get("average_degree", 73.5)
            awd = net_stats.get("average_weighted_degree", 2.6) / max(1.0, avg_degree)
            unsettled = sum(1 for q in engine._queues.values() if not q.is_empty())

            day_data["systems"][sys_name] = {
                "tor": system_tor,
                "settled_count": daily_stats["settled_count"],
                "failed_count": daily_stats["failed_count"],
                "value_settled": total_value,
                "submitted_value": submitted,
                "zona1_value": daily_stats["zona1_value"],
                "zona2_value": daily_stats["zona2_value"],
                "zona3_value": zona3_val,
                "throughput_zona3": throughput_z3,
                "queue_ratio": queue_ratio,
                "average_degree": avg_degree,
                "awd": awd,
                "avg_koneksi": int(net_stats.get("n_edges", 4620)),
                "vol_ic": float(net_stats.get("degree_std", 30.0) * 5),
                "system_utilization": _compute_system_utilization(
                    daily_stats["settled_count"], ticks_per_day, sys_name
                ),
                "unsettled_banks": unsettled,
                "network_stats": net_stats,
            }

        primary = day_data["systems"].get(
            "rtgs", day_data["systems"].get(self.systems[0], {})
        )
        day_data.update({
            "tor": primary.get("tor", 1.7),
            "average_degree": primary.get("average_degree", 73.5),
            "awd": primary.get("awd", 2.6),
            "avg_koneksi": primary.get("avg_koneksi", 4620),
            "vol_ic": primary.get("vol_ic", 188.0),
            "system_utilization": primary.get("system_utilization", 24.0),
            "qr": primary.get("queue_ratio", 4.7),
            "throughput_zona3": primary.get("throughput_zona3", 27.5),
            "unsettled_banks": primary.get("unsettled_banks", 0),
        })

        return day_data

    # ------------------------------------------------------------------
    # Heatmap aggregation
    # ------------------------------------------------------------------

    def _compute_heatmap(
        self,
        daily_results: list[dict[str, Any]],
    ) -> dict[str, dict[str, list[float]]]:
        """Aggregate daily metrics into monthly heatmap data."""
        nb_indicators = [
            "tor", "average_degree", "awd", "avg_koneksi",
            "vol_ic", "system_utilization", "qr", "throughput_zona3",
        ]
        pmkt_indicators = ["tor", "average_degree", "throughput_zona3", "qr"]

        nb_data: dict[str, list[float]] = {k: [] for k in nb_indicators}
        pmkt_data: dict[str, list[float]] = {k: [] for k in pmkt_indicators}

        window_size = 30
        n_days = len(daily_results)
        n_windows = max(1, (n_days + window_size - 1) // window_size)

        for w in range(n_windows):
            start = w * window_size
            end = min(start + window_size, n_days)
            window = daily_results[start:end]

            for ind in nb_indicators:
                vals = [d.get(ind, 0.0) for d in window if d.get(ind) is not None]
                nb_data[ind].append(float(np.mean(vals)) if vals else 0.0)

            for ind in pmkt_indicators:
                vals = [d.get(ind, 0.0) for d in window if d.get(ind) is not None]
                pmkt_data[ind].append(float(np.mean(vals)) if vals else 0.0)

        return {"nb": nb_data, "pmkt": pmkt_data}

    # ------------------------------------------------------------------
    # Synthetic series generation
    # ------------------------------------------------------------------

    def _generate_synthetic_series(
        self,
        n_days: int,
        scenario: str,
    ) -> dict[str, list[float]]:
        """Generate synthetic monthly time-series calibrated to historical data.

        Calibration targets (Bank Indonesia Jan-Dec 2025):
        - tor:                mean ~1.7,    std ~0.4
        - average_degree:     mean ~73.5,   std ~1.5
        - awd:                mean ~2.6,    std ~0.3
        - avg_koneksi:        mean ~4620,   std ~60
        - vol_ic:             mean ~188,    std ~35
        - system_utilization: mean ~24.0,   std ~1.2
        - qr:                 mean ~4.7,    std ~0.6
        - throughput_zona3:   mean ~27.5,   std ~1.5
        """
        rng = np.random.default_rng(self.seed + 7919)
        shifts = _SCENARIO_SHIFTS.get(scenario, {})
        n_months = max(1, (n_days + 29) // 30)
        series: dict[str, list[float]] = {}

        for indicator, calib in _CALIB.items():
            mu = calib["mean"] + shifts.get(indicator, 0.0)
            sigma = calib["std"]
            vals = _generate_ar1_series(rng, n=n_months, mu=mu, sigma=sigma, ar1=0.45)
            vals = _apply_constraints(vals, indicator)
            series[indicator] = [round(float(v), 4) for v in vals]

        return series

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_stress_events_from_scenario(
        self,
        scenario: str,
        scenario_params: dict[str, Any],
        n_days: int,
    ) -> list[Any]:
        try:
            from ..scenarios.controller import ScenarioController
            ctrl = ScenarioController(self.config_dir)
            return ctrl.build_stress_events(scenario, scenario_params)
        except Exception:
            return []

    def _build_market_state(
        self,
        sys_name: str,
        t_min: float,
        active_stress: list[Any],
        past_ticks: list[TickResult],
    ) -> MarketState:
        sys_agents = self._agents[sys_name]
        total_liquidity = sum(agent.liquidity for agent in sys_agents.values())

        stress_level = 0.0
        agent_events: list[StressEvent] = []
        for se in active_stress:
            magnitude = float(getattr(se, "magnitude", 0.0))
            stress_level = max(stress_level, magnitude)
            affected_ids = []
            for b in getattr(se, "affected_banks", []):
                try:
                    affected_ids.append(int(b))
                except (ValueError, TypeError):
                    pass
            event_type_obj = getattr(se, "event_type", None)
            event_type_str = (
                event_type_obj.value
                if hasattr(event_type_obj, "value")
                else str(event_type_obj or "liquidity_shock")
            )
            agent_events.append(
                StressEvent(
                    event_type=event_type_str,
                    magnitude=magnitude,
                    affected_banks=affected_ids,
                    timestamp=t_min,
                )
            )

        if len(past_ticks) >= 5:
            recent = past_ticks[-5:]
            recent_settled = sum(r.settled_count for r in recent)
            recent_total = recent_settled + sum(r.queued_count for r in recent)
            if recent_total > 0 and recent_settled / recent_total < 0.5:
                stress_level = min(1.0, stress_level + 0.15)

        zona = 1
        if t_min >= 360:
            zona = 3
        elif t_min >= 180:
            zona = 2

        return MarketState(
            system_liquidity=total_liquidity,
            stress_level=stress_level,
            time_of_day_zone=zona,
            active_stress_events=agent_events,
        )

    def _restore_eod_liquidity(
        self,
        agent: BankAgent,
        engine: SettlementEngine,
        sys_name: str,
    ) -> None:
        agent.credit_used = max(0.0, agent.credit_used * 0.10)
        gap = agent.params.initial_liquidity - agent.liquidity
        if gap > 0.0:
            agent.liquidity += gap * 0.80
        engine._balances[str(agent.bank_id)] = agent.liquidity

    def _build_network_snapshots(self) -> dict[str, dict[str, Any]]:
        snapshots: dict[str, dict[str, Any]] = {}
        sys_name = "rtgs" if "rtgs" in self._networks else (self.systems[0] if self.systems else None)
        if sys_name is None:
            return snapshots

        G = self._networks.get(sys_name)
        if G is None:
            return snapshots

        nodes = []
        for nid in G.nodes():
            bank_type = G.nodes[nid].get("bank_type", "periphery")
            deg = G.in_degree(nid) + G.out_degree(nid)
            wd = (
                sum(d.get("weight", 0.0) for _, _, d in G.in_edges(nid, data=True))
                + sum(d.get("weight", 0.0) for _, _, d in G.out_edges(nid, data=True))
            )
            nodes.append({
                "id": str(nid),
                "tier": bank_type,
                "degree": deg,
                "weighted_degree": round(wd, 2),
                "systemic_importance": round(min(1.0, wd / max(1.0, wd * 10)), 4),
                "risk_zone": "normal",
            })

        edges = []
        for u, v, data in list(G.edges(data=True))[:500]:
            edges.append({
                "source": str(u),
                "target": str(v),
                "weight": round(float(data.get("weight", 1.0)), 2),
                "transaction_count": 1,
                "value": round(float(data.get("weight", 1.0)), 2),
            })

        metrics = PaymentNetwork.get_network_stats(G)
        snapshots["latest"] = {
            "nodes": nodes,
            "edges": edges,
            "metrics": {k: round(float(v), 4) for k, v in metrics.items()},
        }
        return snapshots

    def _run_contagion_analysis(self) -> dict[str, Any]:
        sys_name = "rtgs" if "rtgs" in self._networks else (self.systems[0] if self.systems else None)
        if sys_name is None:
            return {}

        G = self._networks.get(sys_name)
        if G is None:
            return {}

        try:
            from ..contagion.debtrank import DebtRankEngine
            engine = DebtRankEngine(max_rounds=10)
            nodes = list(G.nodes())
            if not nodes:
                return {}

            degrees = {n: G.in_degree(n) + G.out_degree(n) for n in nodes}
            top_node = max(degrees, key=lambda n: degrees[n])
            result = engine.simulate_debtrank(G, [top_node], loss_given_default=0.6)

            top5 = sorted(degrees, key=lambda n: degrees[n], reverse=True)[:5]
            importance: dict[str, float] = {}
            for node in top5:
                r = engine.simulate_debtrank(G, [node], loss_given_default=0.6)
                importance[str(node)] = round(r.debtrank_score, 4)

            per_round = [
                {
                    "round": rm["round"],
                    "shocked": [str(top_node)],
                    "affected": [str(b) for b in list(result.affected_banks)[:10]],
                    "loss_pct": round(rm["system_loss_pct"], 4),
                    "debtrank": round(rm["total_distress"], 4),
                }
                for rm in result.per_round_metrics[:5]
            ]

            return {
                "initial_bank": str(top_node),
                "final_debtrank": round(result.debtrank_score, 4),
                "total_affected": len(result.affected_banks),
                "system_loss_pct": round(result.system_loss_pct, 4),
                "rounds": per_round,
                "systemic_importance": importance,
            }
        except Exception:
            return {}

    def _generate_periods(self, n_days: int) -> list[str]:
        n_months = max(1, (n_days + 29) // 30)
        periods = []
        year, month = 2025, 1
        for _ in range(n_months):
            periods.append(f"{year}M{month}")
            month += 1
            if month > 12:
                month = 1
                year += 1
        return periods

    def _merge_daily_into_series(
        self,
        series: dict[str, list[float]],
        daily_results: list[dict[str, Any]],
        n_days: int,
    ) -> dict[str, list[float]]:
        indicator_map = {
            "tor": "tor",
            "average_degree": "average_degree",
            "awd": "awd",
            "avg_koneksi": "avg_koneksi",
            "vol_ic": "vol_ic",
            "system_utilization": "system_utilization",
            "qr": "qr",
            "throughput_zona3": "throughput_zona3",
        }

        window = 30
        n_months = max(1, (n_days + window - 1) // window)
        merged = dict(series)

        for ind_key, day_key in indicator_map.items():
            monthly_vals = []
            for m in range(n_months):
                start = m * window
                end = min(start + window, n_days)
                window_days = daily_results[start:end]
                vals = [
                    d.get(day_key)
                    for d in window_days
                    if d.get(day_key) is not None and d.get(day_key, 0) > 0
                ]
                if vals:
                    monthly_vals.append(round(float(np.mean(vals)), 4))
                elif merged.get(ind_key) and m < len(merged[ind_key]):
                    monthly_vals.append(merged[ind_key][m])
                else:
                    monthly_vals.append(_CALIB.get(ind_key, {"mean": 0.0})["mean"])
            merged[ind_key] = monthly_vals

        return merged

    def _load_config(self) -> dict[str, Any]:
        defaults: dict[str, Any] = {"trading_day_minutes": 510.0}
        if self.config_dir is not None and _YAML_AVAILABLE:
            cfg_file = self.config_dir / "simulation.yaml"
            if cfg_file.exists():
                try:
                    with open(cfg_file, "r", encoding="utf-8") as fh:
                        user_cfg = yaml.safe_load(fh) or {}
                    defaults.update(user_cfg)
                except Exception:
                    pass
        return defaults


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _apply_scenario_stress_event(
    stress_event: Any,
    agents: dict[int, BankAgent],
    sys_name: str,
) -> None:
    """Apply a scenario-level stress event to agents."""
    magnitude = float(getattr(stress_event, "magnitude", 0.0))
    affected_systems = getattr(stress_event, "affected_systems", [])
    if affected_systems and sys_name not in affected_systems:
        return

    event_type_obj = getattr(stress_event, "event_type", None)
    event_type_str = (
        event_type_obj.value
        if hasattr(event_type_obj, "value")
        else str(event_type_obj or "liquidity_shock")
    )

    affected_bank_ids_raw = getattr(stress_event, "affected_banks", [])
    affected_int_ids: set[int] = set()
    for b in affected_bank_ids_raw:
        try:
            affected_int_ids.add(int(b))
        except (ValueError, TypeError):
            pass

    for bid, agent in agents.items():
        indirect_factor = 1.0 if (not affected_int_ids or bid in affected_int_ids) else 0.15
        agent_se = StressEvent(
            event_type=event_type_str,
            magnitude=magnitude * indirect_factor,
            affected_banks=[bid] if indirect_factor == 1.0 else [],
            timestamp=0.0,
        )
        agent.respond_to_stress(agent_se)


def _compute_system_utilization(
    settled_count: int,
    ticks_per_day: int,
    system: str,
) -> float:
    """Approximate system utilization as a percentage."""
    capacity_per_tick = {"rtgs": 50, "fast": 200, "raja": 20}
    cap = capacity_per_tick.get(system, 50) * ticks_per_day
    if cap <= 0:
        return 0.0
    return min(100.0, (settled_count / cap) * 100.0)


def _generate_ar1_series(
    rng: np.random.Generator,
    n: int,
    mu: float,
    sigma: float,
    ar1: float = 0.45,
) -> np.ndarray:
    """Generate an AR(1) time-series with given mean and standard deviation."""
    innovations_std = sigma * np.sqrt(max(0.0, 1 - ar1 ** 2))
    series = np.zeros(n)
    if n == 0:
        return series
    series[0] = mu + rng.normal(0, sigma)
    for t in range(1, n):
        series[t] = mu + ar1 * (series[t - 1] - mu) + rng.normal(0, innovations_std)
    return series


def _apply_constraints(vals: np.ndarray, indicator: str) -> np.ndarray:
    """Apply physical domain constraints to a generated series."""
    bounds: dict[str, tuple[float, float]] = {
        "tor":                  (0.5, 5.0),
        "average_degree":       (60.0, 90.0),
        "awd":                  (1.5, 4.0),
        "avg_koneksi":          (4_000.0, 5_500.0),
        "vol_ic":               (50.0, 400.0),
        "system_utilization":   (5.0, 40.0),
        "qr":                   (1.0, 12.0),
        "throughput_zona3":     (10.0, 55.0),
    }
    lo, hi = bounds.get(indicator, (-np.inf, np.inf))
    return np.clip(vals, lo, hi)
