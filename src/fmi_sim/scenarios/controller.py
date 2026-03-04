"""Scenario controller for FMI stress-test orchestration."""
from __future__ import annotations
import yaml
from pathlib import Path
from typing import Any
from .stress_events import StressEvent, StressEventType


SCENARIO_REGISTRY: dict[str, dict[str, Any]] = {
    "baseline": {
        "description": "Normal operating conditions",
        "expected_zone": "normal",
        "stress_events": [],
        "agent_modifiers": {},
    },
    "liquidity_squeeze": {
        "description": "Sudden reduction in interbank liquidity",
        "expected_zone": "siaga",
        "stress_events": ["liquidity_squeeze"],
        "agent_modifiers": {
            "payment_urgency_multiplier": 0.6,
            "zone_timing_shift": 0.15,
            "liquidity_hoarding_factor": 0.40,
        },
        "expected_indicators": {
            "tor": "siaga",
            "throughput_zona3": "siaga",
            "unsettled_banks": "waspada",
        },
    },
    "counterparty_withdrawal": {
        "description": "Major bank reduces counterparty exposure",
        "expected_zone": "siaga",
        "stress_events": ["counterparty_withdrawal"],
        "agent_modifiers": {
            "network_contraction": 0.15,
            "counterparty_reduction": 0.25,
        },
        "expected_indicators": {
            "average_degree": "siaga",
            "awd": "siaga",
            "avg_koneksi": "waspada",
            "volatility_interconnectedness": "siaga",
        },
    },
    "infrastructure_disruption": {
        "description": "Partial system outage affecting settlement",
        "expected_zone": "siaga",
        "stress_events": ["infrastructure_disruption"],
        "agent_modifiers": {},
        "expected_indicators": {
            "system_availability": "siaga",
            "system_utilization": "krisis",
            "incidents": ">MTPD",
        },
    },
    "contagion_cascade": {
        "description": "Bank failure triggers cascading settlement failures",
        "expected_zone": "krisis",
        "stress_events": ["contagion_cascade"],
        "agent_modifiers": {
            "liquidity_hoarding_factor": 0.60,
        },
        "expected_indicators": {
            "unsettled_banks": "krisis",
            "average_degree": "krisis",
            "tor": "krisis",
        },
    },
    "cyber_incident": {
        "description": "Cyber attack affecting participant connectivity",
        "expected_zone": "siaga",
        "stress_events": ["cyber_incident"],
        "agent_modifiers": {},
        "expected_indicators": {
            "reject_fast_dana": "krisis",
            "stability_index_participant_fast": "siaga",
            "avg_degree_fast": "siaga",
        },
    },
}


class ScenarioController:
    """
    Orchestrates simulation scenarios for stress testing.
    Each scenario modifies agent behavior, network topology,
    and/or infrastructure parameters.
    """

    def __init__(self, config_dir: str | Path | None = None):
        self.config_dir = Path(config_dir) if config_dir else None
        self._scenarios = dict(SCENARIO_REGISTRY)
        if self.config_dir:
            self._load_yaml_scenarios()

    def _load_yaml_scenarios(self) -> None:
        """Load additional scenarios from YAML config directory."""
        scenarios_dir = self.config_dir / "scenarios"
        if not scenarios_dir.exists():
            return
        for yaml_file in scenarios_dir.glob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            name = data.get("name", yaml_file.stem)
            self._scenarios[name] = data

    def get_scenario(self, name: str) -> dict[str, Any]:
        """Get scenario configuration by name."""
        if name not in self._scenarios:
            raise ValueError(
                f"Unknown scenario '{name}'. "
                f"Available: {list(self._scenarios.keys())}"
            )
        return self._scenarios[name]

    def list_scenarios(self) -> list[str]:
        """Return list of available scenario names."""
        return list(self._scenarios.keys())

    def build_stress_events(
        self, scenario_name: str, scenario_params: dict[str, Any] | None = None
    ) -> list[StressEvent]:
        """Build StressEvent objects for a named scenario."""
        scenario = self.get_scenario(scenario_name)
        events: list[StressEvent] = []
        params = scenario_params or {}

        for event_name in scenario.get("stress_events", []):
            event = self._create_event(event_name, params)
            if event:
                events.append(event)

        return events

    def _create_event(
        self, event_name: str, params: dict[str, Any]
    ) -> StressEvent | None:
        """Factory method for creating stress events."""
        creators = {
            "liquidity_squeeze": StressEvent.liquidity_squeeze,
            "counterparty_withdrawal": StressEvent.counterparty_withdrawal,
            "infrastructure_disruption": StressEvent.infrastructure_disruption,
            "contagion_cascade": StressEvent.contagion_cascade,
            "cyber_incident": StressEvent.cyber_incident,
        }
        creator = creators.get(event_name)
        if creator is None:
            return None
        # Filter params relevant to this creator
        try:
            import inspect
            sig = inspect.signature(creator)
            relevant = {
                k: v for k, v in params.items()
                if k in sig.parameters
            }
            return creator(**relevant)
        except Exception:
            return creator()

    def get_agent_modifiers(self, scenario_name: str) -> dict[str, float]:
        """Get behavioral modifiers for agent model."""
        scenario = self.get_scenario(scenario_name)
        return scenario.get("agent_modifiers", {})

    def get_expected_indicators(self, scenario_name: str) -> dict[str, str]:
        """Get expected risk zone outcomes per indicator."""
        scenario = self.get_scenario(scenario_name)
        return scenario.get("expected_indicators", {})

    def validate_outcome(
        self, scenario_name: str, actual_zones: dict[str, str]
    ) -> dict[str, bool]:
        """Validate simulation outcome matches scenario expectations."""
        expected = self.get_expected_indicators(scenario_name)
        results = {}
        for indicator, expected_zone in expected.items():
            actual = actual_zones.get(indicator, "unknown")
            results[indicator] = actual == expected_zone
        return results
