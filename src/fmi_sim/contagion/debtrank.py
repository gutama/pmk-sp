"""
DebtRank contagion simulation for FMI systemic risk analysis.

DebtRank is a network-based measure of systemic importance that quantifies
how much economic distress propagates through the interbank network when
one or more banks are shocked.

Reference:
    Battiston et al. (2012). DebtRank: Too central to fail? Financial networks,
    the FED and systemic risk. Scientific Reports, 2, 541.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import networkx as nx


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ContagionResult:
    """Result of a DebtRank contagion simulation.

    Attributes
    ----------
    rounds:
        Number of propagation rounds executed until convergence or max rounds.
    affected_banks:
        Set of node identifiers that ended with distress level > 0.
    system_loss_pct:
        Aggregate economic loss as a percentage of total system equity (0–100).
    debtrank_score:
        The DebtRank score: total fraction of system value rendered
        economically distressed (0–1).
    per_round_metrics:
        List of per-round metrics dictionaries.  Each entry contains:

        * ``round`` — int: round index (1-based).
        * ``newly_distressed`` — list: nodes that crossed the distress
          threshold this round.
        * ``mean_distress`` — float: mean distress level across all nodes.
        * ``total_distress`` — float: sum of distress levels.
        * ``system_loss_pct`` — float: cumulative system loss percentage
          at end of this round.
    """

    rounds: int
    affected_banks: set[Any]
    system_loss_pct: float
    debtrank_score: float
    per_round_metrics: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DebtRankEngine
# ---------------------------------------------------------------------------


class DebtRankEngine:
    """Simulates financial contagion using the DebtRank algorithm.

    The DebtRank algorithm iteratively propagates distress through the
    interbank network.  At each step the distress level of each bank is
    updated based on the distress of its creditors weighted by their
    relative exposure.

    Parameters
    ----------
    max_rounds:
        Maximum number of propagation rounds.  Iteration stops earlier if
        no node's distress changes by more than ``convergence_tol``.
    convergence_tol:
        Convergence tolerance.  If the maximum change in any node's
        distress in a round is below this value, propagation stops.
    distress_threshold:
        Distress level above which a node is considered "affected".
        Default 0.05 (5 % distress).
    """

    def __init__(
        self,
        max_rounds: int = 50,
        convergence_tol: float = 1e-6,
        distress_threshold: float = 0.05,
    ) -> None:
        self.max_rounds = max_rounds
        self.convergence_tol = convergence_tol
        self.distress_threshold = distress_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate_debtrank(
        self,
        network: nx.DiGraph,
        shocked_nodes: list[Any],
        loss_given_default: float = 0.6,
    ) -> ContagionResult:
        """Run the DebtRank algorithm on the given network.

        Initial shock is applied to ``shocked_nodes`` by setting their
        distress levels to ``loss_given_default``.  The distress then
        propagates through the network for up to ``max_rounds`` rounds.

        The update rule is::

            h_i(t+1) = min(1, h_i(t) + Σ_j W_ji * h_j(t) * (1 - h_i(t)))

        where ``W_ji`` is the relative exposure weight from node ``j`` to
        node ``i``, and the sum runs over all predecessors ``j`` of ``i``
        that were *not* in the initial shocked set (to avoid double-counting
        in subsequent rounds).

        Parameters
        ----------
        network:
            Directed interbank exposure graph.  An edge ``(i, j)`` with
            weight ``w`` means bank ``i`` has an exposure of ``w`` to
            bank ``j`` (i.e. bank ``j`` owes ``w`` to bank ``i``).  If
            edges do not have a ``weight`` attribute a weight of 1.0 is
            assumed.
        shocked_nodes:
            List of initially shocked bank identifiers.
        loss_given_default:
            Fraction of value lost when a bank defaults (0–1).  Applied as
            the initial distress level for shocked nodes.

        Returns
        -------
        ContagionResult

        Examples
        --------
        >>> import networkx as nx
        >>> G = nx.DiGraph()
        >>> G.add_edge('A', 'B', weight=0.5)
        >>> G.add_edge('B', 'C', weight=0.3)
        >>> engine = DebtRankEngine()
        >>> result = engine.simulate_debtrank(G, ['A'])
        >>> result.debtrank_score > 0
        True
        """
        nodes = list(network.nodes())
        if not nodes:
            return ContagionResult(
                rounds=0,
                affected_banks=set(),
                system_loss_pct=0.0,
                debtrank_score=0.0,
            )

        # Normalised weights: W_ji = exposure(j->i) / total_assets(j)
        W = self._build_weight_matrix(network, nodes)

        node_index = {node: idx for idx, node in enumerate(nodes)}
        n = len(nodes)

        # Initial distress state
        h = np.zeros(n, dtype=float)
        for node in shocked_nodes:
            if node in node_index:
                h[node_index[node]] = min(1.0, loss_given_default)

        # Track which nodes have been "active" in propagation
        # (initially shocked nodes start as inactive for propagation purposes
        # to avoid self-reinforcement as per standard DebtRank)
        inactive = set(
            node_index[node] for node in shocked_nodes if node in node_index
        )

        per_round_metrics: list[dict[str, Any]] = []
        node_equity = self._get_node_equity(network, nodes)

        for rnd in range(1, self.max_rounds + 1):
            new_h = self._propagate_round(h, W, inactive, n)

            # Check convergence
            delta = np.max(np.abs(new_h - h))

            # Update inactive set: nodes that were shocked and have propagated
            for i in range(n):
                if h[i] > 0 and new_h[i] > 0:
                    inactive.add(i)

            h = new_h

            # Collect metrics
            newly_distressed = [
                nodes[i]
                for i in range(n)
                if h[i] > self.distress_threshold and i not in inactive
            ]
            mean_distress = float(np.mean(h))
            total_distress = float(np.sum(h))
            system_loss = self._compute_system_loss(h, node_equity)

            per_round_metrics.append(
                {
                    "round": rnd,
                    "newly_distressed": newly_distressed,
                    "mean_distress": mean_distress,
                    "total_distress": total_distress,
                    "system_loss_pct": system_loss,
                }
            )

            if delta < self.convergence_tol:
                break

        # Final results
        affected = {
            nodes[i] for i in range(n) if h[i] > self.distress_threshold
        }
        system_loss_pct = self._compute_system_loss(h, node_equity)

        # DebtRank score = (total distress - initial shock distress) / n
        # Normalised by system equity
        total_equity = sum(node_equity.values())
        if total_equity > 0:
            weighted_distress = sum(
                h[node_index[node]] * node_equity.get(node, 1.0)
                for node in nodes
            )
            debtrank_score = weighted_distress / total_equity
        else:
            debtrank_score = float(np.mean(h))

        return ContagionResult(
            rounds=len(per_round_metrics),
            affected_banks=affected,
            system_loss_pct=system_loss_pct,
            debtrank_score=float(debtrank_score),
            per_round_metrics=per_round_metrics,
        )

    def compute_systemic_importance(
        self,
        network: nx.DiGraph,
        loss_given_default: float = 0.6,
    ) -> dict[Any, float]:
        """Compute the systemic importance of each node via DebtRank.

        For each node in the network, a separate single-node shock simulation
        is run.  The resulting DebtRank score is the node's systemic
        importance score.

        Parameters
        ----------
        network:
            Directed interbank exposure network.
        loss_given_default:
            Fraction of value lost at default.

        Returns
        -------
        dict[Any, float]
            Mapping of node identifier to its systemic importance (DebtRank)
            score (0–1).

        Examples
        --------
        >>> import networkx as nx
        >>> G = nx.path_graph(4, create_using=nx.DiGraph())
        >>> engine = DebtRankEngine()
        >>> scores = engine.compute_systemic_importance(G)
        >>> all(0.0 <= v <= 1.0 for v in scores.values())
        True
        """
        importance: dict[Any, float] = {}
        for node in network.nodes():
            result = self.simulate_debtrank(
                network, [node], loss_given_default=loss_given_default
            )
            importance[node] = result.debtrank_score
        return importance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _propagate_round(
        self,
        h: np.ndarray,
        W: np.ndarray,
        inactive: set[int],
        n: int,
    ) -> np.ndarray:
        """Execute one DebtRank propagation round.

        Update rule::

            h_i(t+1) = min(1, h_i(t) + Σ_j W_ji * h_j(t) * (1 - h_i(t)))

        Only nodes ``j`` that are *not* in ``inactive`` contribute to the
        propagation in this round.

        Parameters
        ----------
        h:
            Current distress vector of length ``n``.
        W:
            Weight matrix of shape ``(n, n)`` where ``W[i, j]`` is the
            relative exposure of node ``i`` to node ``j``.
        inactive:
            Set of node indices excluded from transmitting distress this round.
        n:
            Number of nodes.

        Returns
        -------
        numpy.ndarray
            Updated distress vector.
        """
        new_h = h.copy()

        # Create mask: only active nodes propagate
        active_mask = np.ones(n, dtype=float)
        for idx in inactive:
            active_mask[idx] = 0.0

        # Propagation: for each node i, sum W[i,j] * h[j] for active j
        # W[i, j] = relative exposure of i to j (j is debtor of i)
        propagation = W @ (h * active_mask)  # shape: (n,)

        new_h = h + propagation * (1.0 - h)
        new_h = np.clip(new_h, 0.0, 1.0)

        return new_h

    @staticmethod
    def _build_weight_matrix(
        network: nx.DiGraph,
        nodes: list[Any],
    ) -> np.ndarray:
        """Build the normalised weight matrix from the network.

        ``W[i, j]`` = exposure of node ``i`` to node ``j`` normalised by the
        total out-weight of node ``j``.  This means that if ``j`` defaults
        with full distress, it transmits ``W[i, j]`` distress to ``i``.

        Parameters
        ----------
        network:
            Directed interbank network.
        nodes:
            Ordered list of nodes (defines matrix row/column ordering).

        Returns
        -------
        numpy.ndarray
            Weight matrix of shape ``(n, n)``.
        """
        n = len(nodes)
        node_index = {node: idx for idx, node in enumerate(nodes)}
        W = np.zeros((n, n), dtype=float)

        # Compute total out-weight per node (total assets / exposure extended)
        out_totals: dict[Any, float] = {}
        for node in nodes:
            total = sum(
                d.get("weight", 1.0) for _, _, d in network.out_edges(node, data=True)
            )
            out_totals[node] = total if total > 0 else 1.0

        # Fill W[i, j]: node i is exposed to node j (edge j -> i means j owes i)
        for src, dst, data in network.edges(data=True):
            w = float(data.get("weight", 1.0))
            i = node_index.get(dst)  # dst is creditor (exposed)
            j = node_index.get(src)  # src is debtor (may default)
            if i is not None and j is not None:
                W[i, j] = w / out_totals[src]

        return W

    @staticmethod
    def _get_node_equity(
        network: nx.DiGraph,
        nodes: list[Any],
    ) -> dict[Any, float]:
        """Extract node equity values from network node attributes.

        Falls back to 1.0 for nodes without an ``equity`` attribute.

        Parameters
        ----------
        network:
            The network graph.
        nodes:
            List of nodes to extract equity for.

        Returns
        -------
        dict[Any, float]
            Mapping from node to equity value.
        """
        equity: dict[Any, float] = {}
        for node in nodes:
            attr = network.nodes[node]
            equity[node] = float(attr.get("equity", attr.get("assets", 1.0)))
        return equity

    @staticmethod
    def _compute_system_loss(
        h: np.ndarray,
        node_equity: dict[Any, float],
    ) -> float:
        """Compute the system-wide loss as a percentage of total equity.

        Parameters
        ----------
        h:
            Distress vector.
        node_equity:
            Mapping from node to equity value.

        Returns
        -------
        float
            Weighted system loss percentage (0–100).
        """
        nodes = list(node_equity.keys())
        total_equity = sum(node_equity.values())
        if total_equity == 0:
            return float(np.mean(h) * 100.0)

        weighted_loss = sum(
            h[i] * node_equity[nodes[i]] for i in range(len(nodes))
        )
        return (weighted_loss / total_equity) * 100.0
