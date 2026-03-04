"""
FMI Simulation Engine — Indicators package.

Public API::

    from fmi_sim.indicators import IndicatorEngine, HeatmapData, ThresholdClassifier

The indicators package provides:

* :class:`ThresholdClassifier` — classify indicator values into risk levels.
* :class:`IndicatorEngine` — compute all FMI indicators from simulation results.
* :class:`HeatmapData` — structured container for heatmap output data.
* :class:`HeatmapRow` — single-indicator row within a heatmap.
"""

from .thresholds import ThresholdClassifier, ThresholdConfig
from .engine import IndicatorEngine, HeatmapData, HeatmapRow

__all__ = [
    "IndicatorEngine",
    "HeatmapData",
    "HeatmapRow",
    "ThresholdClassifier",
    "ThresholdConfig",
]
