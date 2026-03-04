"""Stress event definitions for FMI simulation scenarios."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StressEventType(Enum):
    LIQUIDITY_SQUEEZE = "liquidity_squeeze"
    COUNTERPARTY_WITHDRAWAL = "counterparty_withdrawal"
    INFRASTRUCTURE_DISRUPTION = "infrastructure_disruption"
    CONTAGION_CASCADE = "contagion_cascade"
    CYBER_INCIDENT = "cyber_incident"
    CUSTOM = "custom"


@dataclass
class StressEvent:
    """Represents a stress event that can be injected into the simulation."""
    event_type: StressEventType
    onset_day: int
    magnitude: float                 # 0.0-1.0 normalized severity
    affected_banks: list[str] = field(default_factory=list)
    affected_systems: list[str] = field(default_factory=list)
    duration_days: int = 0
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def is_active(self, current_day: int) -> bool:
        """Check if this event is active on the given simulation day."""
        if self.duration_days == 0:
            return current_day >= self.onset_day
        return self.onset_day <= current_day < self.onset_day + self.duration_days

    @classmethod
    def liquidity_squeeze(
        cls,
        onset_day: int = 5,
        giro_reduction: float = 0.30,
        credit_facility_cut: float = 0.50,
        duration_days: int = 10,
    ) -> "StressEvent":
        return cls(
            event_type=StressEventType.LIQUIDITY_SQUEEZE,
            onset_day=onset_day,
            magnitude=giro_reduction,
            duration_days=duration_days,
            params={
                "giro_reduction": giro_reduction,
                "credit_facility_cut": credit_facility_cut,
            },
            description=f"Liquidity squeeze: {giro_reduction*100:.0f}% giro reduction",
        )

    @classmethod
    def counterparty_withdrawal(
        cls,
        onset_day: int = 3,
        bank_id: str | None = None,
        connection_reduction: float = 0.60,
        duration_days: int = 5,
    ) -> "StressEvent":
        affected = [bank_id] if bank_id else []
        return cls(
            event_type=StressEventType.COUNTERPARTY_WITHDRAWAL,
            onset_day=onset_day,
            magnitude=connection_reduction,
            affected_banks=affected,
            duration_days=duration_days,
            params={
                "connection_reduction": connection_reduction,
                "bank_tier_target": "core",
                "gradual_withdrawal": True,
            },
            description=f"Counterparty withdrawal: {connection_reduction*100:.0f}% connection reduction",
        )

    @classmethod
    def infrastructure_disruption(
        cls,
        onset_day: int = 7,
        affected_system: str = "rtgs",
        outage_duration_minutes: int = 120,
        capacity_reduction: float = 0.60,
    ) -> "StressEvent":
        return cls(
            event_type=StressEventType.INFRASTRUCTURE_DISRUPTION,
            onset_day=onset_day,
            magnitude=capacity_reduction,
            affected_systems=[affected_system],
            duration_days=1,
            params={
                "outage_duration_minutes": outage_duration_minutes,
                "capacity_reduction": capacity_reduction,
                "processing_delay_multiplier": 3.0,
            },
            description=f"Infrastructure disruption: {affected_system.upper()} {capacity_reduction*100:.0f}% capacity reduction",
        )

    @classmethod
    def contagion_cascade(
        cls,
        onset_day: int = 5,
        failing_bank: str = "top_by_degree",
        failure_mode: str = "sudden_stop",
        cascade_rounds: int = 3,
        lgd: float = 0.60,
    ) -> "StressEvent":
        affected = [failing_bank] if failing_bank != "top_by_degree" else []
        return cls(
            event_type=StressEventType.CONTAGION_CASCADE,
            onset_day=onset_day,
            magnitude=lgd,
            affected_banks=affected,
            params={
                "failure_mode": failure_mode,
                "cascade_rounds": cascade_rounds,
                "loss_given_default": lgd,
                "secondary_failure_threshold": 0.20,
            },
            description=f"Contagion cascade: {failure_mode} failure with LGD={lgd}",
        )

    @classmethod
    def cyber_incident(
        cls,
        onset_day: int = 8,
        affected_banks_pct: float = 0.15,
        reconnection_time_hours: float = 4.0,
    ) -> "StressEvent":
        return cls(
            event_type=StressEventType.CYBER_INCIDENT,
            onset_day=onset_day,
            magnitude=affected_banks_pct,
            params={
                "affected_banks_pct": affected_banks_pct,
                "reconnection_time_hours": reconnection_time_hours,
                "data_integrity_impact": True,
                "reject_rate_increase": 0.20,
                "processing_delay_factor": 2.5,
            },
            description=f"Cyber incident affecting {affected_banks_pct*100:.0f}% of participants",
        )
