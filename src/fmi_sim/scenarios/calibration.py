"""Historical calibration routines for FMI simulation."""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Any
import yaml
from pathlib import Path
from scipy import stats


@dataclass
class CalibrationResult:
    """Results of calibration validation."""
    indicator: str
    mean_error_pct: float
    std_error_pct: float
    ks_statistic: float
    ks_pvalue: float
    acf_lag1_simulated: float
    acf_lag1_historical: float
    passed: bool
    details: dict[str, Any]


class HistoricalCalibrator:
    """
    Calibrates simulation output against historical BI heatmap data.

    Validation criteria (from spec):
    - Mean error ≤ 5%
    - Std deviation error ≤ 15%
    - KS test p-value > 0.05
    - ACF(1) match within 0.20
    """

    # Historical data from BI heatmap (Jan-25 to Jan-26)
    HISTORICAL_DATA = {
        "periods": [
            "2025M1", "2025M2", "2025M3", "2025M4", "2025M5", "2025M6",
            "2025M7", "2025M8", "2025M9", "2025M10", "2025M11", "2025M12",
            "2026M1",
        ],
        "tor": [1.77, 1.69, 1.84, 2.56, 2.70, 2.74, 1.79, 1.43, 1.39, 1.32, 1.21, 1.46, 1.31],
        "tor_adj": [1.19, 1.24, 1.40, 1.78, 1.77, 1.65, 1.37, 1.34, 1.35, 1.20, 1.08, 1.38, 1.13],
        "qr": [4.84, 5.24, 4.54, 4.02, 4.05, 3.95, 4.90, 4.76, 4.96, 5.47, 5.93, 4.75, None],
        "throughput_zona3": [25.5, 26.5, 24.1, 27.3, 28.6, 29.2, 29.0, 29.5, 29.0, 27.3, 26.8, 28.7, 26.4],
        "average_degree": [74.07, 72.45, 73.27, 70.75, 71.45, 72.68, 75.05, 73.49, 73.46, 73.94, 72.89, 76.88, 74.71],
        "awd": [2.32, 2.24, 2.38, 2.31, 2.19, 2.58, 2.84, 2.55, 2.89, 3.24, 2.90, 3.16, 2.85],
        "avg_koneksi": [4565, 4545, 4713, 4635, 4702, 4720, 4601, 4592, 4591, 4566, 4565, 4731, 4583],
        "vol_ic": [234, 191, 227, 168, 195, 208, 121, 161, 161, 130, 192, 241, 155],
        "system_utilization": [23.37, 22.42, 25.18, 25.14, 25.08, 25.70, 23.17, 24.36, 24.39, 23.97, 24.04, 27.00, 23.89],
        "unsettled_banks": [0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1],
        "system_availability": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
        "avg_degree_rtgs": [74, 72, 73, 71, 71, 73, 75, 73, 73, 74, 73, 77, 75],
        "avg_degree_fast": [80.0, 81.0, 82.8, 75.2, 77.3, 77.0, 80.0, 79.9, 80.2, 81.1, 81.4, 83.6, 82.8],
        "avg_degree_raja": [61, 63, 66, 64, 62, 65, 64, 65, 65, 64, 63, 63, 63],
        "stability_provider": [99.96, 99.99, 99.99, 99.99, 99.99, 99.98, 99.99, 99.97, 99.99, 99.99, 100.0, 99.99, 99.99],
        "stability_participant": [99.83, 99.80, 99.75, 99.82, 99.79, 99.81, 99.85, 99.90, 99.85, 99.85, 99.85, 99.86, 99.86],
    }

    TOLERANCE = {
        "mean_error_pct": 5.0,
        "std_error_pct": 15.0,
        "ks_pvalue_min": 0.05,
        "acf_lag1_tolerance": 0.20,
    }

    def __init__(self, config_path: str | Path | None = None):
        if config_path:
            self._load_from_yaml(Path(config_path))

    def _load_from_yaml(self, path: Path) -> None:
        """Load historical data from YAML file."""
        if not path.exists():
            return
        with open(path) as f:
            data = yaml.safe_load(f)
        hist = data.get("nb_version", {})
        for key, values in hist.items():
            clean_key = key.replace("_series", "")
            if values:
                self.HISTORICAL_DATA[clean_key] = values

    def get_historical_series(self, indicator: str) -> np.ndarray:
        """Get historical time series for an indicator (excluding None values)."""
        data = self.HISTORICAL_DATA.get(indicator, [])
        return np.array([v for v in data if v is not None], dtype=float)

    def validate(
        self,
        indicator: str,
        simulated_series: list[float] | np.ndarray,
    ) -> CalibrationResult:
        """Validate simulated series against historical data."""
        sim = np.array([v for v in simulated_series if v is not None], dtype=float)
        hist = self.get_historical_series(indicator)

        if len(hist) == 0:
            return CalibrationResult(
                indicator=indicator,
                mean_error_pct=0.0,
                std_error_pct=0.0,
                ks_statistic=0.0,
                ks_pvalue=1.0,
                acf_lag1_simulated=0.0,
                acf_lag1_historical=0.0,
                passed=True,
                details={"note": "No historical data for this indicator"},
            )

        # Use overlapping window if lengths differ
        n = min(len(sim), len(hist))
        sim, hist = sim[:n], hist[:n]

        # Mean error
        hist_mean = np.mean(hist)
        sim_mean = np.mean(sim)
        mean_error_pct = abs(sim_mean - hist_mean) / (abs(hist_mean) + 1e-9) * 100

        # Std error
        hist_std = np.std(hist)
        sim_std = np.std(sim)
        std_error_pct = abs(sim_std - hist_std) / (abs(hist_std) + 1e-9) * 100

        # KS test
        ks_stat, ks_pvalue = stats.ks_2samp(sim, hist)

        # ACF(1)
        acf_sim = float(pd.Series(sim).autocorr(lag=1)) if len(sim) > 2 else 0.0
        acf_hist = float(pd.Series(hist).autocorr(lag=1)) if len(hist) > 2 else 0.0
        acf_sim = acf_sim if not np.isnan(acf_sim) else 0.0
        acf_hist = acf_hist if not np.isnan(acf_hist) else 0.0

        passed = (
            mean_error_pct <= self.TOLERANCE["mean_error_pct"]
            and std_error_pct <= self.TOLERANCE["std_error_pct"]
            and ks_pvalue >= self.TOLERANCE["ks_pvalue_min"]
            and abs(acf_sim - acf_hist) <= self.TOLERANCE["acf_lag1_tolerance"]
        )

        return CalibrationResult(
            indicator=indicator,
            mean_error_pct=mean_error_pct,
            std_error_pct=std_error_pct,
            ks_statistic=ks_stat,
            ks_pvalue=ks_pvalue,
            acf_lag1_simulated=acf_sim,
            acf_lag1_historical=acf_hist,
            passed=passed,
            details={
                "hist_mean": hist_mean,
                "sim_mean": sim_mean,
                "hist_std": hist_std,
                "sim_std": sim_std,
            },
        )

    def validate_all(
        self, simulated_data: dict[str, list[float]]
    ) -> dict[str, CalibrationResult]:
        """Validate all indicators and return summary."""
        results = {}
        for indicator, series in simulated_data.items():
            if indicator in self.HISTORICAL_DATA:
                results[indicator] = self.validate(indicator, series)
        return results

    def compute_adjustment_factors(self) -> dict[str, float]:
        """
        Compute adjustment factors to calibrate simulation parameters.
        Returns scaling factors per indicator.
        """
        return {
            "tor_scale": 1.0,
            "ad_scale": 1.0,
            "awd_scale": 1.0,
            "avg_koneksi_scale": 1.0,
            "su_scale": 1.0,
        }
