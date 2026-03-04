"""
Payment network topology generation and analysis for FMI simulation.

Supports Barabasi-Albert with core-periphery structure calibrated to:
  - BI-RTGS:  ~140 banks, average degree ~74
  - BI-FAST:  ~80  banks, average degree ~80
  - RAJA:     ~70  banks, average degree ~61
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class NetworkParams:
    """Parameters for network generation.

    Attributes:
        n_banks:              Total number of participant banks.
        network_type:         Payment system identifier: 'rtgs', 'fast', or 'raja'.
        n_core:               Number of core (highly-connected) banks.
        n_periphery:          Number of periphery banks (derived from n_banks - n_core).
        target_avg_degree:    Desired mean degree after generation.
        ba_m:                 Barabasi-Albert attachment parameter (edges per new node).
        weight_distribution:  Distribution for edge weights ('lognormal' or 'uniform').
        weight_mu:            Log-mean for lognormal weight distribution.
        weight_sigma:         Log-std for lognormal weight distribution.
        directed:             Whether to generate a directed graph.
        seed:                 Random seed for reproducibility.
    """

    n_banks: int = 140
    network_type: str = "rtgs"
    n_core: int = 20
    n_periphery: int = 120
    target_avg_degree: float = 74.0
    ba_m: int = 5
    weight_distribution: str = "lognormal"
    weight_mu: float = 10.0  # log-mean in IDR billions
    weight_sigma: float = 1.5
    directed: bool = True
    seed: int = 42


# Calibration targets per system
_SYSTEM_DEFAULTS: dict[str, dict[str, Any]] = {
    "rtgs": {
        "n_banks": 140,
        "n_core": 18,
        "target_avg_degree": 74.0,
        "ba_m": 6,
        "weight_mu": 12.0,
        "weight_sigma": 1.6,
    },
    "fast": {
        "n_banks": 80,
        "n_core": 12,
        "target_avg_degree": 80.0,
        "ba_m": 8,
        "weight_mu": 8.0,
        "weight_sigma": 1.3,
    },
    "raja": {
        "n_banks": 70,
        "n_core": 10,
        "target_avg_degree": 61.0,
        "ba_m": 5,
        "weight_mu": 9.5,
        "weight_sigma": 1.4,
    },
}


# ---------------------------------------------------------------------------
# PaymentNetwork
# ---------------------------------------------------------------------------


class PaymentNetwork:
    """Generator and analyser for interbank payment network topologies.

    The network combines a Barabasi-Albert scale-free backbone with an
    explicit core-periphery overlay where core banks are fully connected
    among themselves to replicate the hub-and-spoke structure observed in
    RTGS / BI-FAST / RAJA payment systems.

    Parameters
    ----------
    n_banks:
        Total number of participating banks.
    network_type:
        Payment system: ``'rtgs'``, ``'fast'``, or ``'raja'``.
    """

    def __init__(self, n_banks: int, network_type: str = "rtgs") -> None:
        self.n_banks = n_banks
        self.network_type = network_type.lower()

        # Merge calibration defaults with supplied n_banks
        defaults = _SYSTEM_DEFAULTS.get(self.network_type, _SYSTEM_DEFAULTS["rtgs"]).copy()
        defaults["n_banks"] = n_banks
        defaults["n_periphery"] = n_banks - defaults["n_core"]

        self._defaults = defaults
        self._rng: np.random.Generator | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_topology(self, params: NetworkParams | None = None) -> nx.DiGraph:
        """Generate a directed payment network graph.

        Parameters
        ----------
        params:
            :class:`NetworkParams` overriding defaults.  When ``None`` the
            calibrated defaults for :attr:`network_type` are used.

        Returns
        -------
        nx.DiGraph
            Directed weighted graph with node attributes:
            ``bank_type`` ('core' | 'periphery'), ``bank_id``,
            and edge attribute ``weight`` (transaction volume in IDR bn).
        """
        if params is None:
            params = self._build_default_params()

        self._rng = np.random.default_rng(params.seed)
        random.seed(params.seed)

        n_core = params.n_core
        n_periphery = params.n_banks - n_core

        G = self._generate_core_periphery(
            n_core=n_core,
            n_periphery=n_periphery,
            target_avg_degree=params.target_avg_degree,
        )
        G = self._assign_weights(G, params.weight_distribution)

        # Store params on graph for later inspection
        G.graph["params"] = params
        G.graph["network_type"] = self.network_type
        return G

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _build_default_params(self) -> NetworkParams:
        d = self._defaults
        return NetworkParams(
            n_banks=d["n_banks"],
            network_type=self.network_type,
            n_core=d["n_core"],
            n_periphery=d["n_periphery"],
            target_avg_degree=d["target_avg_degree"],
            ba_m=d["ba_m"],
            weight_distribution="lognormal",
            weight_mu=d["weight_mu"],
            weight_sigma=d["weight_sigma"],
            directed=True,
            seed=42,
        )

    def _generate_core_periphery(
        self,
        n_core: int,
        n_periphery: int,
        target_avg_degree: float,
    ) -> nx.DiGraph:
        """Build a core-periphery directed graph.

        Algorithm
        ---------
        1. Create a complete directed graph among core nodes (hub-hub links).
        2. Use a Barabasi-Albert-like preferential attachment to connect
           periphery nodes to core and other periphery nodes.
        3. Add random periphery-periphery edges to reach ``target_avg_degree``.

        Parameters
        ----------
        n_core:
            Number of core (hub) banks.
        n_periphery:
            Number of periphery banks.
        target_avg_degree:
            Mean in-degree + out-degree target across all nodes.

        Returns
        -------
        nx.DiGraph
        """
        assert self._rng is not None, "_rng must be set before calling this method"
        rng = self._rng

        n_total = n_core + n_periphery
        G = nx.DiGraph()
        G.add_nodes_from(range(n_total))

        # Assign bank type attributes
        for node in range(n_total):
            if node < n_core:
                G.nodes[node]["bank_type"] = "core"
            else:
                G.nodes[node]["bank_type"] = "periphery"
            G.nodes[node]["bank_id"] = node

        # Step 1: Complete directed clique among core nodes
        for i in range(n_core):
            for j in range(n_core):
                if i != j:
                    G.add_edge(i, j)

        # Step 2: Preferential attachment for periphery nodes
        # Each periphery node attaches to m_attach core / high-degree nodes
        m_attach = max(3, int(target_avg_degree * 0.1))
        m_attach = min(m_attach, n_core)

        for p in range(n_core, n_total):
            # Always connect to a random subset of core nodes (spoke-to-hub)
            core_targets = rng.choice(n_core, size=min(m_attach, n_core), replace=False)
            for c in core_targets:
                if not G.has_edge(p, c):
                    G.add_edge(p, c)
                if not G.has_edge(c, p):
                    G.add_edge(c, p)

        # Step 3: Add extra edges to reach target_avg_degree
        current_avg = (2 * G.number_of_edges()) / n_total if n_total > 0 else 0
        extra_edges_needed = max(0, int((target_avg_degree - current_avg) * n_total / 2))

        nodes = list(G.nodes())
        # Degree-proportional sampling for preferential attachment feel
        attempts = 0
        added = 0
        while added < extra_edges_needed and attempts < extra_edges_needed * 10:
            attempts += 1
            # Source: uniform random; target: degree-biased
            src = int(rng.integers(0, n_total))
            degrees = np.array([G.out_degree(v) + 1 for v in nodes], dtype=float)
            probs = degrees / degrees.sum()
            dst = int(rng.choice(nodes, p=probs))
            if src != dst and not G.has_edge(src, dst):
                G.add_edge(src, dst)
                added += 1

        return G

    def _assign_weights(self, G: nx.DiGraph, weight_distribution: str) -> nx.DiGraph:
        """Assign transaction-volume weights to edges.

        Parameters
        ----------
        G:
            Directed graph whose edges will receive a ``weight`` attribute.
        weight_distribution:
            ``'lognormal'`` (default) or ``'uniform'``.

        Returns
        -------
        nx.DiGraph
            Same graph with ``weight`` edge attributes set (IDR billions).
        """
        assert self._rng is not None

        n_edges = G.number_of_edges()
        if n_edges == 0:
            return G

        d = self._defaults
        mu = d["weight_mu"]
        sigma = d["weight_sigma"]

        if weight_distribution == "lognormal":
            weights = self._rng.lognormal(mean=mu, sigma=sigma, size=n_edges)
        elif weight_distribution == "uniform":
            low = np.exp(mu - 2 * sigma)
            high = np.exp(mu + 2 * sigma)
            weights = self._rng.uniform(low=low, high=high, size=n_edges)
        else:
            raise ValueError(f"Unknown weight_distribution: {weight_distribution!r}")

        for (u, v), w in zip(G.edges(), weights):
            G[u][v]["weight"] = float(w)

        # Scale weights: core–core edges should be larger
        for u, v in G.edges():
            u_type = G.nodes[u].get("bank_type", "periphery")
            v_type = G.nodes[v].get("bank_type", "periphery")
            if u_type == "core" and v_type == "core":
                G[u][v]["weight"] *= 3.0  # Core banks transact more

        return G

    # ------------------------------------------------------------------
    # Static utility
    # ------------------------------------------------------------------

    @staticmethod
    def get_network_stats(G: nx.DiGraph) -> dict[str, float]:
        """Compute descriptive statistics for a payment network graph.

        Parameters
        ----------
        G:
            Directed weighted graph.

        Returns
        -------
        dict with keys:
            ``average_degree``        – mean of in-degree + out-degree per node
            ``average_weighted_degree``– mean weighted degree (AWD)
            ``density``               – graph density
            ``n_nodes``               – number of nodes
            ``n_edges``               – number of edges
            ``core_count``            – number of core banks
            ``periphery_count``       – number of periphery banks
            ``clustering_coef``       – average clustering coefficient (undirected)
            ``degree_std``            – std of total degree
            ``max_degree``            – max total degree
            ``min_degree``            – min total degree
        """
        n = G.number_of_nodes()
        if n == 0:
            return {}

        degrees = np.array([G.in_degree(v) + G.out_degree(v) for v in G.nodes()])
        weighted_degrees = np.array(
            [
                sum(d for _, _, d in G.in_edges(v, data="weight", default=0.0))
                + sum(d for _, _, d in G.out_edges(v, data="weight", default=0.0))
                for v in G.nodes()
            ]
        )

        core_count = sum(
            1 for v in G.nodes() if G.nodes[v].get("bank_type") == "core"
        )

        # Clustering on undirected projection
        ug = G.to_undirected()
        try:
            avg_clust = nx.average_clustering(ug)
        except Exception:
            avg_clust = float("nan")

        return {
            "average_degree": float(np.mean(degrees)),
            "average_weighted_degree": float(np.mean(weighted_degrees)),
            "density": nx.density(G),
            "n_nodes": float(n),
            "n_edges": float(G.number_of_edges()),
            "core_count": float(core_count),
            "periphery_count": float(n - core_count),
            "clustering_coef": avg_clust,
            "degree_std": float(np.std(degrees)),
            "max_degree": float(np.max(degrees)) if len(degrees) > 0 else 0.0,
            "min_degree": float(np.min(degrees)) if len(degrees) > 0 else 0.0,
        }
