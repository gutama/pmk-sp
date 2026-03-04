"""Pydantic models for FMI SimEngine API."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional


class SimulationRequest(BaseModel):
    n_banks: int = Field(default=140, ge=10, le=500, description="Number of participant banks")
    n_days: int = Field(default=30, ge=1, le=365, description="Simulation duration in days")
    scenario: str = Field(default="baseline", description="Scenario name")
    scenario_params: dict[str, Any] = Field(default_factory=dict)
    seed: int = Field(default=42, description="Random seed for reproducibility")
    systems: list[str] = Field(default=["rtgs", "fast", "raja"])
    tick_interval_min: int = Field(default=1, ge=1, le=60)


class SimulationStatus(BaseModel):
    simulation_id: str
    status: str   # "pending" | "running" | "completed" | "failed"
    progress_pct: float = 0.0
    current_day: int = 0
    total_days: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class HeatmapCellData(BaseModel):
    value: Optional[float] = None
    risk_zone: str = "normal"   # "normal" | "waspada" | "siaga" | "krisis"
    formatted_value: str = ""


class HeatmapRowData(BaseModel):
    indicator: str
    label: str
    pillar: str
    threshold_waspada: Optional[float] = None
    threshold_siaga: Optional[float] = None
    threshold_krisis: Optional[float] = None
    direction: str = "inc"
    unit: str = ""
    periods: dict[str, HeatmapCellData] = Field(default_factory=dict)


class HeatmapResponse(BaseModel):
    version: str  # "nb" | "pmkt"
    simulation_id: str
    periods: list[str]
    rows: list[HeatmapRowData]
    overall_risk_zone: str = "normal"
    generated_at: str = ""


class TimeSeriesPoint(BaseModel):
    period: str
    value: Optional[float] = None
    risk_zone: str = "normal"


class TimeSeriesResponse(BaseModel):
    simulation_id: str
    indicator: str
    simulated: list[TimeSeriesPoint]
    historical: list[TimeSeriesPoint] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    direction: str = "inc"
    statistics: dict[str, float] = Field(default_factory=dict)


class NetworkNode(BaseModel):
    id: str
    tier: str  # "core" | "periphery"
    degree: int
    weighted_degree: float
    systemic_importance: float
    risk_zone: str = "normal"
    x: Optional[float] = None
    y: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetworkEdge(BaseModel):
    source: str
    target: str
    weight: float
    transaction_count: int = 0
    value: float = 0.0


class NetworkResponse(BaseModel):
    simulation_id: str
    period: str
    system: str
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]
    metrics: dict[str, float] = Field(default_factory=dict)


class ContagionRound(BaseModel):
    round_num: int
    shocked_banks: list[str]
    affected_banks: list[str]
    cumulative_loss_pct: float
    debtrank_score: float
    newly_failed: list[str] = Field(default_factory=list)


class ContagionResponse(BaseModel):
    simulation_id: str
    initial_bank: str
    total_rounds: int
    rounds: list[ContagionRound]
    final_debtrank: float
    total_banks_affected: int
    systemic_importance: dict[str, float] = Field(default_factory=dict)


class ScenarioCompareRequest(BaseModel):
    simulation_ids: list[str] = Field(min_length=2)


class ScenarioCompareResponse(BaseModel):
    simulations: list[dict[str, Any]]
    divergence_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    indicator_comparison: dict[str, dict[str, Any]] = Field(default_factory=dict)
