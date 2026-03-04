"""
PMKT (Protokol Manajemen Krisis Terpadu) specific indicators.

These indicators are specific to the FMI sub-protocol for wholesale
payment systems, covering RTGS, BI-FAST, and RAJA/SKNBI systems.
"""

from __future__ import annotations

from typing import Any

import networkx as nx


# ---------------------------------------------------------------------------
# Stability index
# ---------------------------------------------------------------------------


def compute_stability_index(
    rejection_rate: float,
    processing_time_pct: float,
) -> float:
    """Compute a composite stability index for a payment system.

    The stability index captures two dimensions of operational health:

    * **Rejection rate** — higher rejection rates degrade stability.
    * **Processing time percentile** — if processing times are within
      acceptable bounds (represented as a percentage of the SLA target)
      stability is maintained.

    Formula::

        stability_index = (1 - rejection_rate / 100) * processing_time_pct

    Both inputs are in percentage form (0–100).  A perfect system has
    a rejection rate of 0 % and processing time of 100 % (meaning all
    transactions processed within SLA).

    Parameters
    ----------
    rejection_rate:
        Percentage of submitted transactions that were rejected (0–100).
    processing_time_pct:
        Percentage of transactions processed within the SLA target (0–100).

    Returns
    -------
    float
        Stability index in the range [0, 100].  A value near 100 indicates
        a stable, high-performing system.

    Notes
    -----
    The threshold direction for stability indices is ``'dec'`` (lower is
    worse).

    Examples
    --------
    >>> compute_stability_index(0.0, 100.0)
    100.0
    >>> compute_stability_index(5.0, 99.0)
    94.05
    """
    availability_factor = 1.0 - (rejection_rate / 100.0)
    return availability_factor * processing_time_pct


# ---------------------------------------------------------------------------
# PMKT Velositas
# ---------------------------------------------------------------------------


def compute_pmkt_velositas(sim_result: dict[str, Any]) -> dict[str, Any]:
    """Compute PMKT-specific velocity indicators.

    Extracts and derives the key velocity indicators relevant to the PMKT
    sub-protocol from a simulation result dictionary.

    Indicators computed:

    * ``unsettled_rtgs_dana`` — number of unsettled DANA (liquidity) payments
      in the RTGS queue at end of day.
    * ``reject_fast_dana`` — number of DANA-category transactions rejected by
      BI-FAST during the measurement period.

    Parameters
    ----------
    sim_result:
        Dictionary of simulation outputs for the current period.  Expected
        keys:

        * ``rtgs_queue`` (list | dict): queue entries; the function counts
          entries where ``category == 'DANA'`` or uses the pre-aggregated
          ``unsettled_rtgs_dana`` key directly.
        * ``fast_rejections`` (list | dict): rejection entries; similarly
          uses ``reject_fast_dana`` if available.

    Returns
    -------
    dict[str, Any]
        Dictionary with keys:

        * ``unsettled_rtgs_dana`` — int: count of unsettled DANA RTGS items.
        * ``reject_fast_dana`` — int: count of DANA rejections in BI-FAST.

    Examples
    --------
    >>> result = {'unsettled_rtgs_dana': 3, 'reject_fast_dana': 1}
    >>> compute_pmkt_velositas(result)
    {'unsettled_rtgs_dana': 3, 'reject_fast_dana': 1}
    """
    # If the simulation provides pre-aggregated values, use them directly
    if "unsettled_rtgs_dana" in sim_result and "reject_fast_dana" in sim_result:
        return {
            "unsettled_rtgs_dana": int(sim_result["unsettled_rtgs_dana"]),
            "reject_fast_dana": int(sim_result["reject_fast_dana"]),
        }

    # Otherwise derive from raw queue / rejection lists
    unsettled_rtgs_dana = 0
    rtgs_queue = sim_result.get("rtgs_queue", [])
    if isinstance(rtgs_queue, list):
        unsettled_rtgs_dana = sum(
            1
            for item in rtgs_queue
            if isinstance(item, dict) and item.get("category", "").upper() == "DANA"
        )
    elif isinstance(rtgs_queue, dict):
        unsettled_rtgs_dana = int(rtgs_queue.get("dana_count", 0))

    reject_fast_dana = 0
    fast_rejections = sim_result.get("fast_rejections", [])
    if isinstance(fast_rejections, list):
        reject_fast_dana = sum(
            1
            for item in fast_rejections
            if isinstance(item, dict) and item.get("category", "").upper() == "DANA"
        )
    elif isinstance(fast_rejections, dict):
        reject_fast_dana = int(fast_rejections.get("dana_count", 0))

    return {
        "unsettled_rtgs_dana": unsettled_rtgs_dana,
        "reject_fast_dana": reject_fast_dana,
    }


# ---------------------------------------------------------------------------
# PMKT Contagion / Network
# ---------------------------------------------------------------------------


def compute_pmkt_contagion(networks: dict[str, nx.DiGraph]) -> dict[str, Any]:
    """Compute PMKT-specific contagion / network structure indicators.

    Derives per-system average degree and RTGS availability from the
    payment system network graphs.

    Parameters
    ----------
    networks:
        Dictionary mapping system names to their directed network graphs.
        Recognised keys: ``'rtgs'``, ``'fast'``, ``'raja'``.

    Returns
    -------
    dict[str, Any]
        Dictionary with keys:

        * ``avg_degree_rtgs`` — float: average degree of the RTGS network.
        * ``avg_degree_fast`` — float: average degree of the BI-FAST network.
        * ``avg_degree_raja`` — float: average degree of the RAJA network.
        * ``availability_rtgs`` — float: RTGS network availability proxy
          (ratio of active nodes to total expected participants × 100).

    Examples
    --------
    >>> import networkx as nx
    >>> G_rtgs = nx.DiGraph()
    >>> G_rtgs.add_edges_from([(0, 1), (1, 2), (2, 0)])
    >>> result = compute_pmkt_contagion({'rtgs': G_rtgs})
    >>> result['avg_degree_rtgs']
    1.0
    """

    def _avg_degree(G: nx.DiGraph) -> float:
        n = G.number_of_nodes()
        if n == 0:
            return 0.0
        return G.number_of_edges() / n

    def _availability_rtgs(G: nx.DiGraph) -> float:
        """Proxy: fraction of nodes that have at least one active edge × 100."""
        n = G.number_of_nodes()
        if n == 0:
            return 100.0
        active_nodes = sum(
            1
            for node in G.nodes()
            if G.degree(node) > 0
        )
        return (active_nodes / n) * 100.0

    g_rtgs: nx.DiGraph = networks.get("rtgs", nx.DiGraph())
    g_fast: nx.DiGraph = networks.get("fast", nx.DiGraph())
    g_raja: nx.DiGraph = networks.get("raja", nx.DiGraph())

    return {
        "avg_degree_rtgs": _avg_degree(g_rtgs),
        "avg_degree_fast": _avg_degree(g_fast),
        "avg_degree_raja": _avg_degree(g_raja),
        "availability_rtgs": _availability_rtgs(g_rtgs),
    }


# ---------------------------------------------------------------------------
# PMKT Operational
# ---------------------------------------------------------------------------


def compute_pmkt_operational(sim_result: dict[str, Any]) -> dict[str, Any]:
    """Compute PMKT-specific operational indicators.

    Derives indicators related to non-DANA unsettled items and system
    stability indices from a simulation result dictionary.

    Indicators computed:

    * ``unsettled_rtgs_nondana`` — unsettled non-DANA RTGS payments at EOD.
    * ``stability_index_provider_fast`` — stability index for BI-FAST
      infrastructure providers.
    * ``stability_index_participant_fast`` — stability index for BI-FAST
      participant banks.

    Parameters
    ----------
    sim_result:
        Dictionary of simulation outputs.  Expected keys:

        * ``unsettled_rtgs_nondana`` (int, optional): pre-aggregated count.
        * ``rtgs_queue`` (list | dict, optional): raw queue items with
          ``category`` field.
        * ``fast_provider_rejection_rate`` (float): percentage of provider
          transactions rejected (default 0.0).
        * ``fast_provider_processing_pct`` (float): percentage of provider
          transactions within SLA (default 100.0).
        * ``fast_participant_rejection_rate`` (float): percentage of
          participant transactions rejected (default 0.0).
        * ``fast_participant_processing_pct`` (float): percentage of
          participant transactions within SLA (default 100.0).

    Returns
    -------
    dict[str, Any]
        Dictionary with keys:

        * ``unsettled_rtgs_nondana`` — int.
        * ``stability_index_provider_fast`` — float (0–100).
        * ``stability_index_participant_fast`` — float (0–100).

    Examples
    --------
    >>> result = {
    ...     'unsettled_rtgs_nondana': 2,
    ...     'fast_provider_rejection_rate': 0.05,
    ...     'fast_provider_processing_pct': 99.5,
    ...     'fast_participant_rejection_rate': 0.1,
    ...     'fast_participant_processing_pct': 99.0,
    ... }
    >>> out = compute_pmkt_operational(result)
    >>> 'stability_index_provider_fast' in out
    True
    """
    # Unsettled non-DANA RTGS
    if "unsettled_rtgs_nondana" in sim_result:
        unsettled_nondana = int(sim_result["unsettled_rtgs_nondana"])
    else:
        rtgs_queue = sim_result.get("rtgs_queue", [])
        if isinstance(rtgs_queue, list):
            unsettled_nondana = sum(
                1
                for item in rtgs_queue
                if isinstance(item, dict)
                and item.get("category", "").upper() != "DANA"
            )
        elif isinstance(rtgs_queue, dict):
            unsettled_nondana = int(rtgs_queue.get("nondana_count", 0))
        else:
            unsettled_nondana = 0

    # BI-FAST provider stability
    provider_rejection = float(
        sim_result.get("fast_provider_rejection_rate", 0.0)
    )
    provider_processing = float(
        sim_result.get("fast_provider_processing_pct", 100.0)
    )
    stability_provider = compute_stability_index(
        provider_rejection, provider_processing
    )

    # BI-FAST participant stability
    participant_rejection = float(
        sim_result.get("fast_participant_rejection_rate", 0.0)
    )
    participant_processing = float(
        sim_result.get("fast_participant_processing_pct", 100.0)
    )
    stability_participant = compute_stability_index(
        participant_rejection, participant_processing
    )

    return {
        "unsettled_rtgs_nondana": unsettled_nondana,
        "stability_index_provider_fast": stability_provider,
        "stability_index_participant_fast": stability_participant,
    }
