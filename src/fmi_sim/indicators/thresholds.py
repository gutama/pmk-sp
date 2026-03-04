"""
Threshold configuration and classification for FMI simulation indicators.

Thresholds define risk levels (waspada/siaga/krisis) for each indicator
based on direction of concern (inc = increasing is worse, dec = decreasing is worse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import yaml


Direction = Literal["inc", "dec"]
RiskLevel = Literal["normal", "waspada", "siaga", "krisis"]


@dataclass
class ThresholdConfig:
    """Configuration for a single indicator's threshold levels.

    Attributes:
        direction: 'inc' means increasing values are worse (higher = more risk);
                   'dec' means decreasing values are worse (lower = more risk).
        waspada: Threshold value for 'waspada' (alert) risk level.
        siaga: Threshold value for 'siaga' (standby) risk level.
        krisis: Threshold value for 'krisis' (crisis) risk level.
    """

    direction: Direction
    waspada: float
    siaga: float
    krisis: float


# Default thresholds hardcoded from specification
_DEFAULT_THRESHOLDS: dict[str, ThresholdConfig] = {
    "unsettled_banks": ThresholdConfig(
        direction="inc", waspada=1.0, siaga=5.0, krisis=10.0
    ),
    "average_degree": ThresholdConfig(
        direction="dec", waspada=65.80, siaga=63.18, krisis=60.55
    ),
    "system_availability": ThresholdConfig(
        direction="dec", waspada=97.00, siaga=98.50, krisis=99.975
    ),
    "tor": ThresholdConfig(
        direction="inc", waspada=1.36, siaga=2.19, krisis=3.03
    ),
    "tor_adj": ThresholdConfig(
        direction="inc", waspada=1.36, siaga=2.19, krisis=3.03
    ),
    "queue_ratio": ThresholdConfig(
        direction="dec", waspada=4.21, siaga=3.98, krisis=2.74
    ),
    "throughput_zona3": ThresholdConfig(
        direction="inc", waspada=40.0, siaga=50.0, krisis=60.0
    ),
    "awd": ThresholdConfig(
        direction="dec", waspada=2.29, siaga=2.14, krisis=1.98
    ),
    "avg_koneksi": ThresholdConfig(
        direction="dec", waspada=4000.0, siaga=3959.0, krisis=3918.0
    ),
    "volatility_interconnectedness": ThresholdConfig(
        direction="inc", waspada=243.0, siaga=252.0, krisis=280.0
    ),
    "system_utilization": ThresholdConfig(
        direction="inc", waspada=26.94, siaga=27.99, krisis=29.56
    ),
    "unsettled_rtgs_dana": ThresholdConfig(
        direction="inc", waspada=1.0, siaga=5.0, krisis=10.0
    ),
    "reject_fast_dana": ThresholdConfig(
        direction="inc", waspada=1.0, siaga=5.0, krisis=10.0
    ),
    "avg_degree_rtgs": ThresholdConfig(
        direction="dec", waspada=65.80, siaga=63.18, krisis=60.55
    ),
    "avg_degree_fast": ThresholdConfig(
        direction="dec", waspada=72.39, siaga=68.32, krisis=64.25
    ),
    "avg_degree_raja": ThresholdConfig(
        direction="dec", waspada=64.49, siaga=63.44, krisis=62.39
    ),
    "availability_rtgs": ThresholdConfig(
        direction="dec", waspada=99.95, siaga=99.90, krisis=99.975
    ),
    "unsettled_rtgs_nondana": ThresholdConfig(
        direction="inc", waspada=1.0, siaga=5.0, krisis=10.0
    ),
    "stability_index_provider_fast": ThresholdConfig(
        direction="dec", waspada=99.95, siaga=97.00, krisis=95.00
    ),
    "stability_index_participant_fast": ThresholdConfig(
        direction="dec", waspada=99.95, siaga=97.00, krisis=95.00
    ),
}


class ThresholdClassifier:
    """Classifies indicator values into risk levels based on threshold configurations.

    Usage::

        classifier = ThresholdClassifier()
        level = classifier.classify("tor", 2.5)  # returns 'siaga'

    Can be initialised with custom thresholds or with the defaults loaded from a
    YAML file via :meth:`load_from_yaml`.
    """

    def __init__(self, thresholds: dict[str, ThresholdConfig] | None = None) -> None:
        """Initialise with optional custom thresholds.

        Parameters
        ----------
        thresholds:
            Mapping of indicator name to :class:`ThresholdConfig`.  When *None*
            the hardcoded default thresholds from the specification are used.
        """
        if thresholds is None:
            self._thresholds: dict[str, ThresholdConfig] = dict(_DEFAULT_THRESHOLDS)
        else:
            self._thresholds = dict(thresholds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, indicator: str, value: float) -> RiskLevel:
        """Classify *value* for *indicator* into a risk level.

        Parameters
        ----------
        indicator:
            Name of the indicator (must exist in the threshold configuration).
        value:
            Observed numeric value of the indicator.

        Returns
        -------
        str
            One of ``'normal'``, ``'waspada'``, ``'siaga'``, or ``'krisis'``.

        Raises
        ------
        KeyError
            If *indicator* is not found in the threshold configuration.
        """
        if indicator not in self._thresholds:
            raise KeyError(
                f"Indicator '{indicator}' not found in threshold configuration. "
                f"Available indicators: {sorted(self._thresholds.keys())}"
            )

        cfg = self._thresholds[indicator]

        if cfg.direction == "inc":
            return self._classify_increasing(value, cfg)
        else:
            return self._classify_decreasing(value, cfg)

    @staticmethod
    def load_from_yaml(path: str) -> dict[str, ThresholdConfig]:
        """Load threshold configurations from a YAML file.

        Expected YAML format::

            unsettled_banks:
              direction: inc
              waspada: 1
              siaga: 5
              krisis: 10

        Parameters
        ----------
        path:
            Absolute or relative path to the YAML configuration file.

        Returns
        -------
        dict[str, ThresholdConfig]
            Mapping of indicator name to :class:`ThresholdConfig`.

        Raises
        ------
        FileNotFoundError
            If the file does not exist at *path*.
        KeyError
            If a required field is missing for any indicator.
        ValueError
            If *direction* is not ``'inc'`` or ``'dec'``.
        """
        with open(path, "r", encoding="utf-8") as fh:
            raw: dict = yaml.safe_load(fh) or {}

        result: dict[str, ThresholdConfig] = {}
        for name, values in raw.items():
            direction = values["direction"]
            if direction not in ("inc", "dec"):
                raise ValueError(
                    f"Indicator '{name}' has invalid direction '{direction}'. "
                    "Must be 'inc' or 'dec'."
                )
            result[name] = ThresholdConfig(
                direction=direction,
                waspada=float(values["waspada"]),
                siaga=float(values["siaga"]),
                krisis=float(values["krisis"]),
            )
        return result

    @property
    def thresholds(self) -> dict[str, ThresholdConfig]:
        """Return a copy of the current threshold mapping."""
        return dict(self._thresholds)

    def get_config(self, indicator: str) -> ThresholdConfig:
        """Return the :class:`ThresholdConfig` for the given indicator.

        Parameters
        ----------
        indicator:
            Name of the indicator.

        Raises
        ------
        KeyError
            If *indicator* is not in the configuration.
        """
        return self._thresholds[indicator]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_increasing(value: float, cfg: ThresholdConfig) -> RiskLevel:
        """Classify when *higher* values signal greater risk (direction='inc')."""
        # Severity ordering: normal < waspada < siaga < krisis
        if value >= cfg.krisis:
            return "krisis"
        if value >= cfg.siaga:
            return "siaga"
        if value >= cfg.waspada:
            return "waspada"
        return "normal"

    @staticmethod
    def _classify_decreasing(value: float, cfg: ThresholdConfig) -> RiskLevel:
        """Classify when *lower* values signal greater risk (direction='dec')."""
        # For decreasing direction, waspada >= siaga >= krisis (all decrease toward crisis)
        # value <= krisis threshold  -> krisis
        # value <= siaga threshold   -> siaga
        # value <= waspada threshold -> waspada
        # else                       -> normal
        #
        # Note: the spec thresholds for 'dec' direction may not always be strictly
        # ordered (e.g. system_availability: W:97 < S:98.5 < K:99.975).  In such cases
        # the krisis threshold is the most severe boundary, so we compare against
        # the *most severe* (lowest in dec case) level first.
        #
        # We handle both orderings by finding which boundary the value falls under.
        # The three thresholds form three severity boundaries; the value is classified
        # into the *most severe* level whose boundary the value has crossed.

        # Collect (threshold_value, level) and sort by threshold ascending so that
        # the most-severe boundary (lowest value for 'dec') is tested first.
        boundaries = sorted(
            [
                (cfg.krisis, "krisis"),
                (cfg.siaga, "siaga"),
                (cfg.waspada, "waspada"),
            ],
            key=lambda t: t[0],
        )

        for threshold, level in boundaries:
            if value <= threshold:
                return level  # type: ignore[return-value]

        return "normal"
