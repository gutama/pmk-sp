"""
Indicator Engine for FMI Simulation.

The ``IndicatorEngine`` orchestrates computation of all FMI indicators from
raw simulation results, classifies each indicator's risk level, and packages
the outputs into structured :class:`HeatmapData` objects ready for
visualisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import networkx as nx

from .thresholds import ThresholdClassifier, ThresholdConfig, RiskLevel
from .velositas import (
    compute_tor,
    compute_tor_adjusted,
    compute_queue_ratio,
    compute_throughput_zona3,
)
from .struktur import (
    compute_average_degree,
    compute_avg_connections,
    compute_volatility_interconnectedness,
    compute_interconnectedness_index,
    compute_all_struktur,
)
from .infrastruktur import (
    compute_system_availability,
    compute_system_utilization,
    compute_incidents,
    IncidentRecord,
)
from .pmkt import (
    compute_pmkt_velositas,
    compute_pmkt_contagion,
    compute_pmkt_operational,
    compute_stability_index,
)


# ---------------------------------------------------------------------------
# HeatmapRow / HeatmapData dataclasses
# ---------------------------------------------------------------------------


@dataclass
class HeatmapRow:
    """A single indicator row in the heatmap output.

    Represents the value and risk classification of one indicator across
    multiple time periods.

    Attributes
    ----------
    indicator:
        Canonical indicator name (e.g. ``'tor'``, ``'average_degree'``).
    category:
        High-level category the indicator belongs to (e.g. ``'velositas'``,
        ``'struktur'``, ``'infrastruktur'``, ``'pmkt'``).
    period_values:
        Ordered list of (value, risk_level) tuples, one per simulation
        period/tick.
    current_value:
        Most recent computed value.
    current_level:
        Risk classification for the most recent value.
    """

    indicator: str
    category: str
    period_values: list[tuple[float, RiskLevel]] = field(default_factory=list)
    current_value: float = 0.0
    current_level: RiskLevel = "normal"

    def add_period(self, value: float, level: RiskLevel) -> None:
        """Append a new (value, level) pair and update the current values."""
        self.period_values.append((value, level))
        self.current_value = value
        self.current_level = level

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dictionary for serialisation."""
        return {
            "indicator": self.indicator,
            "category": self.category,
            "current_value": self.current_value,
            "current_level": self.current_level,
            "period_values": [
                {"value": v, "level": lv} for v, lv in self.period_values
            ],
        }


@dataclass
class HeatmapData:
    """Container for all heatmap indicator data, split by protocol version.

    Attributes
    ----------
    nb_version:
        Dictionary of :class:`HeatmapRow` objects for the NB (Nasional /
        generic) protocol version, keyed by indicator name.
    pmkt_version:
        Dictionary of :class:`HeatmapRow` objects for the PMKT sub-protocol
        version, keyed by indicator name.
    metadata:
        Optional metadata dictionary (e.g. simulation period, scenario name).
    """

    nb_version: dict[str, HeatmapRow] = field(default_factory=dict)
    pmkt_version: dict[str, HeatmapRow] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """Return a flat :class:`pandas.DataFrame` of all indicators.

        Each row in the DataFrame represents one indicator (from either
        ``nb_version`` or ``pmkt_version``).  Columns are:

        * ``protocol`` — ``'nb'`` or ``'pmkt'``
        * ``indicator``
        * ``category``
        * ``current_value``
        * ``current_level``
        * ``n_periods`` — number of period observations recorded

        Returns
        -------
        pandas.DataFrame
        """
        records: list[dict[str, Any]] = []

        for indicator, row in self.nb_version.items():
            records.append(
                {
                    "protocol": "nb",
                    "indicator": indicator,
                    "category": row.category,
                    "current_value": row.current_value,
                    "current_level": row.current_level,
                    "n_periods": len(row.period_values),
                }
            )

        for indicator, row in self.pmkt_version.items():
            records.append(
                {
                    "protocol": "pmkt",
                    "indicator": indicator,
                    "category": row.category,
                    "current_value": row.current_value,
                    "current_level": row.current_level,
                    "n_periods": len(row.period_values),
                }
            )

        return pd.DataFrame(records)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "nb_version": {k: v.to_dict() for k, v in self.nb_version.items()},
            "pmkt_version": {k: v.to_dict() for k, v in self.pmkt_version.items()},
            "metadata": self.metadata,
        }

    def get_risk_summary(self) -> dict[str, int]:
        """Return counts of each risk level across all indicators.

        Returns
        -------
        dict[str, int]
            Keys ``'normal'``, ``'waspada'``, ``'siaga'``, ``'krisis'``.
        """
        counts: dict[str, int] = {
            "normal": 0,
            "waspada": 0,
            "siaga": 0,
            "krisis": 0,
        }
        all_rows = list(self.nb_version.values()) + list(self.pmkt_version.values())
        for row in all_rows:
            counts[row.current_level] = counts.get(row.current_level, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# IndicatorEngine
# ---------------------------------------------------------------------------


class IndicatorEngine:
    """Orchestrator that computes all FMI indicators from simulation results.

    Usage::

        from fmi_sim.indicators.thresholds import ThresholdClassifier
        classifier = ThresholdClassifier()
        engine = IndicatorEngine(classifier.thresholds)
        heatmap = engine.compute_all(sim_result)
        df = heatmap.to_dataframe()

    Parameters
    ----------
    thresholds:
        Mapping of indicator name to :class:`ThresholdConfig`.  Typically
        obtained from :class:`~fmi_sim.indicators.thresholds.ThresholdClassifier`.
    """

    def __init__(self, thresholds: dict[str, ThresholdConfig]) -> None:
        self._classifier = ThresholdClassifier(thresholds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_risk_level(self, indicator: str, value: float) -> RiskLevel:
        """Classify a single indicator value into a risk level.

        Delegates to the internal :class:`ThresholdClassifier`.

        Parameters
        ----------
        indicator:
            Indicator name.
        value:
            Observed value.

        Returns
        -------
        str
            One of ``'normal'``, ``'waspada'``, ``'siaga'``, ``'krisis'``.
        """
        try:
            return self._classifier.classify(indicator, value)
        except KeyError:
            return "normal"

    def compute_all(self, sim_result: dict[str, Any]) -> HeatmapData:
        """Compute all indicators and return a fully populated :class:`HeatmapData`.

        Parameters
        ----------
        sim_result:
            Aggregate simulation result dictionary.  The engine extracts
            sub-dictionaries from well-known keys.  Expected top-level keys:

            * ``network`` (:class:`~networkx.DiGraph`) — aggregate payment network.
            * ``networks`` (dict[str, DiGraph]) — per-system networks for PMKT.
            * ``ic_history`` (list[float]) — historical interconnectedness series.
            * ``settled_payments`` (float)
            * ``bank_balances`` (float)
            * ``queued_value`` (float)
            * ``total_submitted_value`` (float)
            * ``zona3_value`` (float)
            * ``total_value`` (float)
            * ``uptime_minutes`` (float)
            * ``total_minutes`` (float)
            * ``actual_load`` (float)
            * ``max_capacity`` (float)
            * ``incidents`` (list[:class:`IncidentRecord`])
            * ``unsettled_banks`` (int)
            * ``awd`` (float)
            * All PMKT keys as accepted by pmkt module functions.

        Returns
        -------
        HeatmapData
            Populated heatmap data object.
        """
        heatmap = HeatmapData(
            metadata=sim_result.get("metadata", {})
        )

        # -- NB Version indicators --
        heatmap.nb_version = self._compute_nb_indicators(sim_result)

        # -- PMKT Version indicators --
        heatmap.pmkt_version = self._compute_pmkt_indicators(sim_result)

        return heatmap

    # ------------------------------------------------------------------
    # NB (generic) indicators
    # ------------------------------------------------------------------

    def _compute_nb_indicators(
        self, sim_result: dict[str, Any]
    ) -> dict[str, HeatmapRow]:
        """Compute indicators for the generic NB protocol version."""
        rows: dict[str, HeatmapRow] = {}

        # --- Velositas ---
        rows.update(self._compute_velositas(sim_result))

        # --- Struktur ---
        rows.update(self._compute_struktur(sim_result))

        # --- Infrastruktur ---
        rows.update(self._compute_infrastruktur(sim_result))

        return rows

    def _compute_velositas(
        self, sim_result: dict[str, Any]
    ) -> dict[str, HeatmapRow]:
        """Compute velositas (velocity) indicators."""
        rows: dict[str, HeatmapRow] = {}

        # TOR
        settled = float(sim_result.get("settled_payments", 0.0))
        balances = float(sim_result.get("bank_balances", 1.0))
        tor_val = compute_tor(settled, balances)
        rows["tor"] = self._make_row("tor", "velositas", tor_val)

        # TOR adjusted
        adj_factor = float(sim_result.get("tor_adjustment_factor", 0.85))
        tor_adj_val = compute_tor_adjusted(tor_val, adj_factor)
        rows["tor_adj"] = self._make_row("tor_adj", "velositas", tor_adj_val)

        # Queue ratio
        queued = float(sim_result.get("queued_value", 0.0))
        total_submitted = float(sim_result.get("total_submitted_value", 0.0))
        queue_ratio_val = compute_queue_ratio(queued, total_submitted)
        rows["queue_ratio"] = self._make_row(
            "queue_ratio", "velositas", queue_ratio_val
        )

        # Throughput zona3
        zona3 = float(sim_result.get("zona3_value", 0.0))
        total_val = float(sim_result.get("total_value", 0.0))
        tp_zona3_val = compute_throughput_zona3(zona3, total_val)
        rows["throughput_zona3"] = self._make_row(
            "throughput_zona3", "velositas", tp_zona3_val
        )

        # AWD (Average Waiting Duration) — taken directly from sim result
        awd_val = float(sim_result.get("awd", 0.0))
        rows["awd"] = self._make_row("awd", "velositas", awd_val)

        # Unsettled banks
        unsettled_banks = float(sim_result.get("unsettled_banks", 0))
        rows["unsettled_banks"] = self._make_row(
            "unsettled_banks", "velositas", unsettled_banks
        )

        return rows

    def _compute_struktur(
        self, sim_result: dict[str, Any]
    ) -> dict[str, HeatmapRow]:
        """Compute struktur (network structure) indicators."""
        rows: dict[str, HeatmapRow] = {}

        G: nx.DiGraph = sim_result.get("network", nx.DiGraph())
        ic_history: list[float] = sim_result.get("ic_history", [])

        struktur = compute_all_struktur(G, ic_history)

        rows["average_degree"] = self._make_row(
            "average_degree", "struktur", struktur["average_degree"]
        )
        rows["avg_koneksi"] = self._make_row(
            "avg_koneksi", "struktur", float(struktur["avg_koneksi"])
        )
        rows["volatility_interconnectedness"] = self._make_row(
            "volatility_interconnectedness",
            "struktur",
            struktur["volatility_interconnectedness"],
        )

        # System utilization from struktur context (also in infrastruktur)
        sys_util = float(sim_result.get("system_utilization", 0.0))
        if sys_util == 0.0:
            actual_load = float(sim_result.get("actual_load", 0.0))
            max_cap = float(sim_result.get("max_capacity", 1.0))
            sys_util = compute_system_utilization(actual_load, max_cap)
        rows["system_utilization"] = self._make_row(
            "system_utilization", "struktur", sys_util
        )

        return rows

    def _compute_infrastruktur(
        self, sim_result: dict[str, Any]
    ) -> dict[str, HeatmapRow]:
        """Compute infrastruktur (infrastructure) indicators."""
        rows: dict[str, HeatmapRow] = {}

        # System availability
        uptime = float(sim_result.get("uptime_minutes", 0.0))
        total_mins = float(sim_result.get("total_minutes", 0.0))
        avail_val = compute_system_availability(uptime, total_mins)
        # Prefer pre-computed if provided
        avail_val = float(sim_result.get("system_availability", avail_val))
        rows["system_availability"] = self._make_row(
            "system_availability", "infrastruktur", avail_val
        )

        return rows

    # ------------------------------------------------------------------
    # PMKT indicators
    # ------------------------------------------------------------------

    def _compute_pmkt_indicators(
        self, sim_result: dict[str, Any]
    ) -> dict[str, HeatmapRow]:
        """Compute indicators for the PMKT sub-protocol version."""
        rows: dict[str, HeatmapRow] = {}

        # PMKT velositas
        pmkt_vel = compute_pmkt_velositas(sim_result)
        rows["unsettled_rtgs_dana"] = self._make_row(
            "unsettled_rtgs_dana",
            "pmkt_velositas",
            float(pmkt_vel["unsettled_rtgs_dana"]),
        )
        rows["reject_fast_dana"] = self._make_row(
            "reject_fast_dana",
            "pmkt_velositas",
            float(pmkt_vel["reject_fast_dana"]),
        )

        # PMKT contagion / network
        networks: dict[str, nx.DiGraph] = sim_result.get("networks", {})
        pmkt_contagion = compute_pmkt_contagion(networks)
        rows["avg_degree_rtgs"] = self._make_row(
            "avg_degree_rtgs",
            "pmkt_contagion",
            pmkt_contagion["avg_degree_rtgs"],
        )
        rows["avg_degree_fast"] = self._make_row(
            "avg_degree_fast",
            "pmkt_contagion",
            pmkt_contagion["avg_degree_fast"],
        )
        rows["avg_degree_raja"] = self._make_row(
            "avg_degree_raja",
            "pmkt_contagion",
            pmkt_contagion["avg_degree_raja"],
        )
        rows["availability_rtgs"] = self._make_row(
            "availability_rtgs",
            "pmkt_contagion",
            pmkt_contagion["availability_rtgs"],
        )

        # PMKT operational
        pmkt_ops = compute_pmkt_operational(sim_result)
        rows["unsettled_rtgs_nondana"] = self._make_row(
            "unsettled_rtgs_nondana",
            "pmkt_operational",
            float(pmkt_ops["unsettled_rtgs_nondana"]),
        )
        rows["stability_index_provider_fast"] = self._make_row(
            "stability_index_provider_fast",
            "pmkt_operational",
            pmkt_ops["stability_index_provider_fast"],
        )
        rows["stability_index_participant_fast"] = self._make_row(
            "stability_index_participant_fast",
            "pmkt_operational",
            pmkt_ops["stability_index_participant_fast"],
        )

        return rows

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_row(
        self,
        indicator: str,
        category: str,
        value: float,
    ) -> HeatmapRow:
        """Create a :class:`HeatmapRow` with a single period observation."""
        level = self.classify_risk_level(indicator, value)
        row = HeatmapRow(
            indicator=indicator,
            category=category,
            current_value=value,
            current_level=level,
        )
        row.add_period(value, level)
        return row
