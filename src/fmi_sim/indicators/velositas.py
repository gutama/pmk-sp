"""
Velositas (velocity/flow) indicators for FMI simulation.

These indicators measure the speed and efficiency of payment settlement
within the wholesale payment system.
"""

from __future__ import annotations

from typing import Sequence


def compute_tor(
    settled_payments: float,
    bank_balances: float,
) -> float:
    """Compute the Turnover Ratio (TOR).

    TOR measures how many times the aggregate bank balance is turned over
    by settled payments within the measurement period.

    Formula::

        TOR = settled_payments / bank_balances

    Parameters
    ----------
    settled_payments:
        Total value of payments settled during the period.
    bank_balances:
        Total aggregate bank balance (liquidity) available in the system.

    Returns
    -------
    float
        Turnover ratio. A value > 1 means settled volume exceeds available
        balance, indicating high liquidity recycling. Returns 0.0 if
        ``bank_balances`` is zero to avoid division by zero.

    Examples
    --------
    >>> compute_tor(1_000_000, 500_000)
    2.0
    """
    if bank_balances == 0.0:
        return 0.0
    return settled_payments / bank_balances


def compute_tor_adjusted(
    tor: float,
    adjustment_factor: float = 0.85,
) -> float:
    """Compute the adjusted Turnover Ratio (TOR_adj).

    Applies a conservative adjustment factor to the raw TOR, typically
    accounting for intraday credit, repo, or other liquidity facilities
    that inflate the apparent turnover.

    Formula::

        TOR_adj = TOR * adjustment_factor

    Parameters
    ----------
    tor:
        Raw turnover ratio as returned by :func:`compute_tor`.
    adjustment_factor:
        Multiplier to apply. Default 0.85 (85 %) per specification.

    Returns
    -------
    float
        Adjusted turnover ratio.

    Examples
    --------
    >>> compute_tor_adjusted(2.0)
    1.7
    """
    return tor * adjustment_factor


def compute_queue_ratio(
    queued_value: float,
    total_submitted_value: float,
) -> float:
    """Compute the Queue Ratio.

    Measures the proportion of submitted payment value that is currently
    sitting in the queue (not yet settled). A declining ratio signals
    worsening settlement velocity.

    Formula::

        queue_ratio = (total_submitted_value - queued_value) / total_submitted_value * 100

    Expressed as the *settled percentage*, so that a higher number means
    more of the submitted value has been settled (better).

    Parameters
    ----------
    queued_value:
        Total value of payments currently in the settlement queue.
    total_submitted_value:
        Total value of payments submitted during the measurement period.

    Returns
    -------
    float
        Settled percentage (0–100). Returns 100.0 if total_submitted_value
        is zero (nothing to queue).

    Notes
    -----
    The threshold direction for ``queue_ratio`` is ``'dec'``, meaning lower
    values indicate higher risk (less of the submitted value has settled).

    Examples
    --------
    >>> compute_queue_ratio(100.0, 1000.0)
    90.0
    """
    if total_submitted_value == 0.0:
        return 100.0
    settled_value = total_submitted_value - queued_value
    return (settled_value / total_submitted_value) * 100.0


def compute_throughput_zona3(
    zona3_value: float,
    total_value: float,
) -> float:
    """Compute the throughput percentage for Zone 3 (end-of-day settlement window).

    Zone 3 is the final settlement window of the operating day. A high
    concentration of settlement activity in Zone 3 indicates that banks
    are delaying payments, creating systemic liquidity risk.

    Formula::

        throughput_zona3 = (zona3_value / total_value) * 100

    Parameters
    ----------
    zona3_value:
        Total value of payments settled during Zone 3.
    total_value:
        Total value of payments settled across all zones.

    Returns
    -------
    float
        Percentage of total settled value occurring in Zone 3 (0–100).
        Returns 0.0 if ``total_value`` is zero.

    Notes
    -----
    The threshold direction for ``throughput_zona3`` is ``'inc'``, meaning
    a higher Zone 3 concentration signals increased risk of end-of-day gridlock.

    Examples
    --------
    >>> compute_throughput_zona3(500.0, 1000.0)
    50.0
    """
    if total_value == 0.0:
        return 0.0
    return (zona3_value / total_value) * 100.0
