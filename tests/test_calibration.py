"""Tests for historical calibration."""
import pytest
import numpy as np
from fmi_sim.scenarios.calibration import HistoricalCalibrator, CalibrationResult


class TestHistoricalCalibrator:
    @pytest.fixture
    def calibrator(self):
        return HistoricalCalibrator()

    def test_get_historical_series(self, calibrator):
        tor_series = calibrator.get_historical_series("tor")
        assert len(tor_series) > 0
        assert all(isinstance(v, float) for v in tor_series)

    def test_historical_tor_values(self, calibrator):
        tor = calibrator.get_historical_series("tor")
        # From spec: Jan-25 = 1.77, mean should be around 1.7
        assert abs(np.mean(tor) - 1.7) < 0.5

    def test_validate_perfect_match(self, calibrator):
        # Perfect match should pass all criteria
        hist = list(calibrator.get_historical_series("tor"))
        result = calibrator.validate("tor", hist)
        assert isinstance(result, CalibrationResult)
        assert result.mean_error_pct < 5.0

    def test_validate_far_off_fails(self, calibrator):
        # Values way off should fail
        bad_series = [100.0] * 13  # TOR of 100 is way off
        result = calibrator.validate("tor", bad_series)
        assert result.passed is False

    def test_validate_all_returns_dict(self, calibrator):
        sim_data = {
            "tor": [1.77, 1.69, 1.84, 2.56, 2.70, 2.74, 1.79, 1.43, 1.39, 1.32, 1.21, 1.46, 1.31],
            "average_degree": [74, 72, 73, 71, 71, 73, 75, 73, 73, 74, 73, 77, 75],
        }
        results = calibrator.validate_all(sim_data)
        assert "tor" in results
        assert "average_degree" in results
        assert all(isinstance(v, CalibrationResult) for v in results.values())

    def test_validate_unknown_indicator(self, calibrator):
        # Unknown indicator should not fail but return passed=True
        result = calibrator.validate("nonexistent", [1.0, 2.0, 3.0])
        assert result.passed is True

    def test_calibration_result_fields(self, calibrator):
        result = calibrator.validate("system_utilization",
                                     [23.37, 22.42, 25.18, 25.14, 25.08, 25.70,
                                      23.17, 24.36, 24.39, 23.97, 24.04, 27.00, 23.89])
        assert hasattr(result, "mean_error_pct")
        assert hasattr(result, "ks_pvalue")
        assert hasattr(result, "acf_lag1_simulated")
        assert result.mean_error_pct >= 0
        assert 0.0 <= result.ks_pvalue <= 1.0
