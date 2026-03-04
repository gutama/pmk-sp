"""Intraday liquidity management for FMI simulation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Calibration constants (Jan-2025 BI-RTGS reference)
# ---------------------------------------------------------------------------

CALIB_TOR_JAN25: float = 1.77
CALIB_QR_JAN25: float = 4.84

# Target zona distribution (fraction of daily transactions per zone)
ZONA_TARGET_PCT: dict[int, tuple[float, float]] = {
    1: (0.25, 0.30),  # 25–30 %
    2: (0.40, 0.45),  # 40–45 %
    3: (0.00, 0.40),  # ≤ 40 % (floor 0 as it is a max constraint)
}


# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------


@dataclass
class LiquidityRecommendation:
    """Strategic intraday liquidity recommendation for a bank.

    Attributes:
        action:  One of ``'hold'``, ``'release'``, ``'inject'``, ``'monitor'``.
        amount:  IDR-billion amount associated with the recommended action.
        reason:  Human-readable explanation of the recommendation.
    """

    action: str   # 'hold' | 'release' | 'inject' | 'monitor'
    amount: float
    reason: str


# ---------------------------------------------------------------------------
# LiquidityManager
# ---------------------------------------------------------------------------


class LiquidityManager:
    """Computes intraday liquidity metrics and provides strategic recommendations.

    This class is designed to be stateless for its core metric computations:
    all static/metric methods derive outputs purely from the arguments passed
    to them.  It can therefore be instantiated once and shared across all
    banks/systems in a simulation.

    Metrics implemented
    -------------------
    - **TOR** (Turnover Ratio): throughput relative to average opening/closing balance.
    - **TOR Adjusted**: TOR scaled by a conservative adjustment factor.
    - **Queue Ratio**: fraction of submitted value that has *not* settled.
    - **Throughput Zona 3**: share of daily settlement volume occurring in Zone 3.
    - **System TOR**: system-wide weighted TOR across all banks.
    """

    # ------------------------------------------------------------------
    # Individual metrics
    # ------------------------------------------------------------------

    @staticmethod
    def compute_tor(
        settled_value: float,
        opening_balance: float,
        closing_balance: float,
    ) -> float:
        """Compute the Turnover Ratio (TOR) for a single bank.

        Formula::

            TOR = settled_value / avg(opening_balance, closing_balance)

        A TOR > 1 indicates the bank recycled liquidity (settled more than
        its average balance), which is efficient but can signal stress if
        excessively high.

        Parameters
        ----------
        settled_value:
            Total value of payments settled during the period (IDR bn).
        opening_balance:
            Bank balance at the start of the period (IDR bn).
        closing_balance:
            Bank balance at the end of the period (IDR bn).

        Returns
        -------
        float
            TOR value (0 if denominator is zero or negative).
        """
        avg_balance = (opening_balance + closing_balance) / 2.0
        if avg_balance <= 0.0:
            return 0.0
        return settled_value / avg_balance

    @staticmethod
    def compute_tor_adjusted(
        tor: float,
        adjustment_factor: float = 0.85,
    ) -> float:
        """Compute the adjusted TOR.

        Applies a conservative scaling factor to the raw TOR, accounting
        for intraday credit and repo facilities that inflate apparent turnover.

        Formula::

            TOR_adj = TOR * adjustment_factor

        Parameters
        ----------
        tor:
            Raw TOR as returned by :meth:`compute_tor`.
        adjustment_factor:
            Conservative multiplier (default 0.85 per BI specification).

        Returns
        -------
        float
            Adjusted TOR.
        """
        return tor * adjustment_factor

    @staticmethod
    def compute_queue_ratio(
        peak_queued_value: float,
        total_submitted_value: float,
    ) -> float:
        """Compute the Queue Ratio.

        Measures the proportion of submitted value that has *not* been
        settled (currently queued).  A high ratio indicates settlement
        congestion.

        Formula::

            queue_ratio = (peak_queued_value / total_submitted_value) * 100

        Parameters
        ----------
        peak_queued_value:
            Peak (or current) value of payments sitting in the queue (IDR bn).
        total_submitted_value:
            Total value of payments submitted during the measurement period (IDR bn).

        Returns
        -------
        float
            Queue ratio as a percentage (0–100).  Returns 0.0 if
            ``total_submitted_value`` is zero.
        """
        if total_submitted_value <= 0.0:
            return 0.0
        return (peak_queued_value / total_submitted_value) * 100.0

    @staticmethod
    def compute_throughput_zona3(
        zona3_value: float,
        total_value: float,
    ) -> float:
        """Compute the Zona 3 throughput share.

        A high Zona 3 concentration means banks are deferring settlement
        toward end-of-day, increasing gridlock and operational risk.

        Formula::

            throughput_zona3 = (zona3_value / total_value) * 100

        Parameters
        ----------
        zona3_value:
            Total value settled during Zona 3 (IDR bn).
        total_value:
            Total value settled across all zones (IDR bn).

        Returns
        -------
        float
            Percentage of daily settled value occurring in Zona 3 (0–100).
            Returns 0.0 if ``total_value`` is zero.
        """
        if total_value <= 0.0:
            return 0.0
        return (zona3_value / total_value) * 100.0

    # ------------------------------------------------------------------
    # Strategic recommendation
    # ------------------------------------------------------------------

    def manage_intraday_liquidity(
        self,
        bank_id: str,
        available_balance: float,
        pending_obligations: float,
        expected_inflows: float,
    ) -> LiquidityRecommendation:
        """Produce a strategic intraday liquidity recommendation for a bank.

        Decision framework
        ------------------
        1. If ``available_balance`` covers pending obligations with ≥ 150 %
           headroom, recommend releasing excess liquidity into the market.
        2. If balance covers obligations but headroom is < 150 %,
           recommend monitoring (no action needed yet).
        3. If balance is insufficient but expected inflows will cover the gap,
           recommend holding (wait for inflows before settling).
        4. If balance + inflows are insufficient, recommend injecting liquidity
           (draw on credit facility or central-bank repo).

        Parameters
        ----------
        bank_id:
            Identifier of the bank (used in the recommendation message only).
        available_balance:
            Current uncommitted balance (IDR bn).
        pending_obligations:
            Total value of queued outbound payments (IDR bn).
        expected_inflows:
            Anticipated incoming payments within the current tick window (IDR bn).

        Returns
        -------
        LiquidityRecommendation
        """
        if pending_obligations <= 0.0:
            return LiquidityRecommendation(
                action="monitor",
                amount=0.0,
                reason=f"Bank {bank_id}: no pending obligations; continue monitoring.",
            )

        coverage_ratio = available_balance / pending_obligations

        if coverage_ratio >= 1.5:
            # Ample liquidity — release excess to improve system efficiency
            excess = available_balance - pending_obligations
            release_amount = excess * 0.5  # release half the excess
            return LiquidityRecommendation(
                action="release",
                amount=release_amount,
                reason=(
                    f"Bank {bank_id}: coverage ratio {coverage_ratio:.2f}x. "
                    "Releasing excess liquidity to market."
                ),
            )

        if coverage_ratio >= 1.0:
            # Sufficient but tight — monitor
            return LiquidityRecommendation(
                action="monitor",
                amount=0.0,
                reason=(
                    f"Bank {bank_id}: coverage ratio {coverage_ratio:.2f}x. "
                    "Sufficient balance; continue monitoring."
                ),
            )

        # Insufficient balance — check whether inflows will cover the gap
        gap = pending_obligations - available_balance
        if expected_inflows >= gap:
            return LiquidityRecommendation(
                action="hold",
                amount=gap,
                reason=(
                    f"Bank {bank_id}: shortfall {gap:.1f} IDR bn covered by "
                    f"expected inflows {expected_inflows:.1f} IDR bn. "
                    "Hold payments until inflows arrive."
                ),
            )

        # Inflows insufficient — need to inject liquidity
        injection_needed = gap - expected_inflows
        return LiquidityRecommendation(
            action="inject",
            amount=injection_needed,
            reason=(
                f"Bank {bank_id}: shortfall {gap:.1f} IDR bn; inflows cover only "
                f"{expected_inflows:.1f} IDR bn. "
                f"Inject {injection_needed:.1f} IDR bn (credit/repo)."
            ),
        )

    # ------------------------------------------------------------------
    # System-wide metric
    # ------------------------------------------------------------------

    def compute_system_tor(
        self,
        all_bank_data: dict[str, dict[str, Any]],
    ) -> float:
        """Compute the system-wide TOR as a weighted average across all banks.

        Each bank contributes its individual TOR weighted by its average balance
        (banks with larger average balances receive higher weight).

        Parameters
        ----------
        all_bank_data:
            Mapping of bank_id -> data dict.  Each data dict must contain:

            * ``settled_value``    – float (IDR bn settled by this bank).
            * ``opening_balance``  – float (IDR bn at day start).
            * ``closing_balance``  – float (IDR bn at day end).

        Returns
        -------
        float
            Weighted system-wide TOR (0.0 if no valid data).

        Examples
        --------
        >>> lm = LiquidityManager()
        >>> data = {
        ...     "bank_1": {"settled_value": 100.0, "opening_balance": 50.0, "closing_balance": 60.0},
        ...     "bank_2": {"settled_value": 200.0, "opening_balance": 100.0, "closing_balance": 90.0},
        ... }
        >>> tor = lm.compute_system_tor(data)
        >>> tor > 0
        True
        """
        total_weight = 0.0
        weighted_tor_sum = 0.0

        for bank_id, data in all_bank_data.items():
            settled = float(data.get("settled_value", 0.0))
            opening = float(data.get("opening_balance", 0.0))
            closing = float(data.get("closing_balance", 0.0))

            avg_balance = (opening + closing) / 2.0
            if avg_balance <= 0.0:
                continue

            bank_tor = settled / avg_balance
            weighted_tor_sum += bank_tor * avg_balance
            total_weight += avg_balance

        if total_weight <= 0.0:
            return 0.0

        return weighted_tor_sum / total_weight
