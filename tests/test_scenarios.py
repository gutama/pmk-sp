"""Tests for scenario controller and stress events."""
import pytest
from fmi_sim.scenarios.controller import ScenarioController
from fmi_sim.scenarios.stress_events import StressEvent, StressEventType


class TestScenarioController:
    @pytest.fixture
    def controller(self):
        return ScenarioController()

    def test_list_scenarios(self, controller):
        scenarios = controller.list_scenarios()
        assert "baseline" in scenarios
        assert "liquidity_squeeze" in scenarios
        assert "contagion_cascade" in scenarios

    def test_get_baseline(self, controller):
        scenario = controller.get_scenario("baseline")
        assert scenario["expected_zone"] == "normal"

    def test_get_unknown_raises(self, controller):
        with pytest.raises(ValueError):
            controller.get_scenario("nonexistent_scenario")

    def test_build_stress_events_baseline(self, controller):
        events = controller.build_stress_events("baseline")
        assert events == []

    def test_build_stress_events_liquidity_squeeze(self, controller):
        events = controller.build_stress_events("liquidity_squeeze")
        assert len(events) > 0
        assert events[0].event_type == StressEventType.LIQUIDITY_SQUEEZE

    def test_build_stress_events_contagion(self, controller):
        events = controller.build_stress_events("contagion_cascade")
        assert len(events) > 0

    def test_agent_modifiers_baseline(self, controller):
        mods = controller.get_agent_modifiers("baseline")
        assert isinstance(mods, dict)

    def test_agent_modifiers_liquidity_squeeze(self, controller):
        mods = controller.get_agent_modifiers("liquidity_squeeze")
        assert "payment_urgency_multiplier" in mods
        assert mods["payment_urgency_multiplier"] < 1.0

    def test_expected_indicators(self, controller):
        expected = controller.get_expected_indicators("liquidity_squeeze")
        assert "tor" in expected
        assert expected["tor"] == "siaga"

    def test_validate_outcome(self, controller):
        actual = {"tor": "siaga", "throughput_zona3": "siaga"}
        results = controller.validate_outcome("liquidity_squeeze", actual)
        assert results["tor"] is True


class TestStressEvents:
    def test_liquidity_squeeze_factory(self):
        event = StressEvent.liquidity_squeeze(onset_day=5, giro_reduction=0.30)
        assert event.event_type == StressEventType.LIQUIDITY_SQUEEZE
        assert event.params["giro_reduction"] == 0.30

    def test_contagion_factory(self):
        event = StressEvent.contagion_cascade(onset_day=3, lgd=0.60)
        assert event.event_type == StressEventType.CONTAGION_CASCADE
        assert event.params["loss_given_default"] == 0.60

    def test_is_active(self):
        event = StressEvent.liquidity_squeeze(onset_day=5, duration_days=10)
        assert not event.is_active(3)
        assert event.is_active(5)
        assert event.is_active(10)
        assert not event.is_active(15)

    def test_cyber_incident(self):
        event = StressEvent.cyber_incident(affected_banks_pct=0.15)
        assert event.event_type == StressEventType.CYBER_INCIDENT
        assert event.magnitude == pytest.approx(0.15)
