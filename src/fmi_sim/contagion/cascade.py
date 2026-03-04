"""
Cascade failure simulation for FMI systemic risk analysis.

The cascade simulator models how failures propagate through the interbank
network round-by-round, where each failing bank may trigger additional
failures in connected banks when exposure thresholds are exceeded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx


# ---------------------------------------------------------------------------
# CascadeRound dataclass
# ---------------------------------------------------------------------------


@dataclass
class CascadeRound:
    """Results for a single round of cascade failure simulation.

    Attributes
    ----------
    round_num:
        Round index (1-based).
    newly_affected:
        Set of bank identifiers that newly failed or became critically
        distressed in this round.
    cumulative_affected:
        Set of all bank identifiers that have failed or are critically
        distressed up to and including this round.
    system_loss:
        Estimated system-wide loss as a fraction of total system equity
        (0–1) at the end of this round.
    """

    round_num: int
    newly_affected: set[Any]
    cumulative_affected: set[Any]
    system_loss: float


# ---------------------------------------------------------------------------
# CascadeSimulator
# ---------------------------------------------------------------------------


class CascadeSimulator:
    """Simulates round-by-round cascade failure propagation.

    In each round, each non-failed bank examines whether its exposure to
    already-failed banks exceeds its solvency threshold.  If it does, the
    bank also fails and may trigger further failures in subsequent rounds.

    Parameters
    ----------
    solvency_threshold:
        Fraction of a bank's equity that can be lost before it fails.
        Default 0.10 (10 %).
    exposure_weight:
        Name of the edge attribute used as the exposure amount.
        Default ``'weight'``.
    """

    def __init__(
        self,
        solvency_threshold: float = 0.10,
        exposure_weight: str = "weight",
    ) -> None:
        self.solvency_threshold = solvency_threshold
        self.exposure_weight = exposure_weight

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate_cascade(
        self,
        network: nx.DiGraph,
        failing_banks: list[Any],
        n_rounds: int = 10,
    ) -> list[CascadeRound]:
        """Simulate cascade failure propagation.

        Starting from the set of initially failing banks, iterates for up to
        ``n_rounds`` rounds.  In each round, every solvent bank checks whether
        its cumulative loss from exposures to all currently-failed banks
        exceeds its solvency threshold.  If so, it also fails.

        Simulation stops early if no new failures occur in a round.

        Parameters
        ----------
        network:
            Directed interbank exposure graph.  An edge ``(i, j)`` with
            weight ``w`` means bank ``i`` has an exposure of ``w`` to
            bank ``j``.
        failing_banks:
            List of bank identifiers that fail at time 0 (initial shock).
        n_rounds:
            Maximum number of propagation rounds.

        Returns
        -------
        list[CascadeRound]
            Ordered list of :class:`CascadeRound` objects, one per round.
            The first entry (round 1) records the initial shock.

        Examples
        --------
        >>> import networkx as nx
        >>> G = nx.DiGraph()
        >>> G.add_edge('A', 'B', weight=0.5)
        >>> G.add_edge('B', 'C', weight=0.3)
        >>> G.nodes['A']['equity'] = 1.0
        >>> G.nodes['B']['equity'] = 1.0
        >>> G.nodes['C']['equity'] = 1.0
        >>> sim = CascadeSimulator(solvency_threshold=0.4)
        >>> rounds = sim.simulate_cascade(G, ['A'])
        >>> rounds[0].cumulative_affected == {'A'}
        True
        """
        nodes = set(network.nodes())
        node_equity = self._get_node_equity(network)
        total_equity = sum(node_equity.values())

        # Seed with initial failures
        cumulative_failed: set[Any] = set(
            b for b in failing_banks if b in nodes
        )
        results: list[CascadeRound] = []

        # Round 0 / initial shock
        initial_loss = self._compute_system_loss(cumulative_failed, node_equity, total_equity)
        results.append(
            CascadeRound(
                round_num=1,
                newly_affected=set(cumulative_failed),
                cumulative_affected=set(cumulative_failed),
                system_loss=initial_loss,
            )
        )

        for rnd in range(2, n_rounds + 2):
            newly_failed: set[Any] = set()

            for node in nodes - cumulative_failed:
                # Compute total exposure loss from already-failed banks
                loss = self._compute_node_loss(
                    network, node, cumulative_failed, node_equity
                )
                if loss >= self.solvency_threshold:
                    newly_failed.add(node)

            if not newly_failed:
                # No new failures — cascade has stabilised
                break

            cumulative_failed = cumulative_failed | newly_failed
            system_loss = self._compute_system_loss(
                cumulative_failed, node_equity, total_equity
            )

            results.append(
                CascadeRound(
                    round_num=rnd,
                    newly_affected=set(newly_failed),
                    cumulative_affected=set(cumulative_failed),
                    system_loss=system_loss,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_node_loss(
        self,
        network: nx.DiGraph,
        node: Any,
        failed_banks: set[Any],
        node_equity: dict[Any, float],
    ) -> float:
        """Compute the fractional equity loss for ``node`` due to failed counterparties.

        The loss is the sum of exposures to all failed counterparties
        normalised by ``node``'s own equity.

        Parameters
        ----------
        network:
            Interbank exposure graph.
        node:
            The bank whose loss is being computed.
        failed_banks:
            Set of currently-failed bank identifiers.
        node_equity:
            Mapping of node to equity value.

        Returns
        -------
        float
            Fractional loss (0–∞).  A value >= ``solvency_threshold`` means
            the node should fail.
        """
        equity = node_equity.get(node, 1.0)
        if equity <= 0:
            return 1.0  # Already insolvent

        total_exposure_loss = 0.0
        for failed in failed_banks:
            # Edge (node -> failed): node has lent to failed bank
            if network.has_edge(node, failed):
                exposure = float(
                    network[node][failed].get(self.exposure_weight, 1.0)
                )
                total_exposure_loss += exposure

        return total_exposure_loss / equity

    @staticmethod
    def _compute_system_loss(
        failed_banks: set[Any],
        node_equity: dict[Any, float],
        total_equity: float,
    ) -> float:
        """Compute system-wide loss fraction from failed banks.

        Parameters
        ----------
        failed_banks:
            Set of failed bank identifiers.
        node_equity:
            Equity mapping.
        total_equity:
            Sum of all node equity values.

        Returns
        -------
        float
            Loss as a fraction of total system equity (0–1).
        """
        if total_equity <= 0:
            return 0.0
        failed_equity = sum(node_equity.get(b, 0.0) for b in failed_banks)
        return failed_equity / total_equity

    @staticmethod
    def _get_node_equity(network: nx.DiGraph) -> dict[Any, float]:
        """Extract equity values from node attributes.

        Falls back to 1.0 for nodes without an ``equity`` or ``assets``
        attribute.

        Parameters
        ----------
        network:
            Interbank network.

        Returns
        -------
        dict[Any, float]
            Node-to-equity mapping.
        """
        equity: dict[Any, float] = {}
        for node, attrs in network.nodes(data=True):
            equity[node] = float(
                attrs.get("equity", attrs.get("assets", 1.0))
            )
        return equity
