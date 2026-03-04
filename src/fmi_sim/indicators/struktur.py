"""
Struktur (network structure) indicators for FMI simulation.

These indicators measure the topology and connectivity of the interbank
payment network, capturing systemic risk arising from structural dependencies.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import networkx as nx


def compute_average_degree(G: nx.DiGraph) -> float:
    """Compute the average degree of the payment network.

    Defined as the ratio of edges to nodes:  |E| / |V|.

    For a directed graph this equals the average out-degree (which equals
    the average in-degree).  A higher average degree generally indicates a
    more densely connected network.

    Parameters
    ----------
    G:
        Directed payment network graph.  Nodes represent banks; edges
        represent payment flows.

    Returns
    -------
    float
        Average degree.  Returns 0.0 for an empty graph.

    Notes
    -----
    The threshold direction for ``average_degree`` is ``'dec'``, meaning a
    decreasing average degree signals growing fragmentation and higher risk.

    Examples
    --------
    >>> import networkx as nx
    >>> G = nx.DiGraph()
    >>> G.add_edges_from([(1, 2), (2, 3), (3, 1)])
    >>> compute_average_degree(G)
    1.0
    """
    n_nodes = G.number_of_nodes()
    if n_nodes == 0:
        return 0.0
    return G.number_of_edges() / n_nodes


def compute_avg_weighted_degree(
    G: nx.DiGraph,
    weight: str = "value",
) -> float:
    """Compute the average weighted out-degree of the network.

    The weighted degree of a node is the sum of edge weights on its
    outgoing edges.  The average is taken across all nodes.

    Parameters
    ----------
    G:
        Directed payment network graph with numeric edge attributes.
    weight:
        Name of the edge attribute to use as weight. Defaults to ``'value'``.

    Returns
    -------
    float
        Mean weighted out-degree across all nodes.  Returns 0.0 for an
        empty graph or if no edges carry the requested weight attribute.

    Examples
    --------
    >>> import networkx as nx
    >>> G = nx.DiGraph()
    >>> G.add_edge(1, 2, value=100.0)
    >>> G.add_edge(2, 3, value=200.0)
    >>> compute_avg_weighted_degree(G)
    100.0
    """
    n_nodes = G.number_of_nodes()
    if n_nodes == 0:
        return 0.0

    total_weight = sum(
        d.get(weight, 0.0) for _, _, d in G.out_edges(data=True)
    )
    return total_weight / n_nodes


def compute_avg_connections(G: nx.DiGraph) -> int:
    """Compute the average number of unique counterparties per bank.

    For each node the number of *distinct* neighbours (both in- and
    out-neighbours) is counted.  The function returns the rounded mean
    across all nodes.

    Parameters
    ----------
    G:
        Directed payment network graph.

    Returns
    -------
    int
        Average number of unique connections per node.  Returns 0 for an
        empty graph.

    Notes
    -----
    This corresponds to the ``avg_koneksi`` indicator in the specification,
    whose threshold direction is ``'dec'``.

    Examples
    --------
    >>> import networkx as nx
    >>> G = nx.DiGraph()
    >>> G.add_edges_from([(1, 2), (1, 3), (2, 3)])
    >>> compute_avg_connections(G)
    2
    """
    if G.number_of_nodes() == 0:
        return 0

    total = 0
    for node in G.nodes():
        # Unique neighbours: predecessors union successors
        neighbours = set(G.predecessors(node)) | set(G.successors(node))
        total += len(neighbours)

    return round(total / G.number_of_nodes())


def compute_volatility_interconnectedness(
    ic_series: list[float],
    window: int = 20,
) -> float:
    """Compute the rolling volatility of the interconnectedness index.

    Takes a time series of interconnectedness values and returns the
    standard deviation over the most recent ``window`` observations,
    scaled to a basis-point measure (multiply by 10 000).

    Parameters
    ----------
    ic_series:
        Ordered list of historical interconnectedness index values.  The
        most recent value is last.
    window:
        Number of most-recent observations to include in the volatility
        calculation. Defaults to 20.

    Returns
    -------
    float
        Rolling standard deviation of interconnectedness multiplied by
        10 000, expressed in basis points.  Returns 0.0 if fewer than
        2 observations are available.

    Notes
    -----
    The threshold direction is ``'inc'``, meaning higher volatility
    signals elevated systemic risk.

    Examples
    --------
    >>> series = [0.5] * 20
    >>> compute_volatility_interconnectedness(series)
    0.0
    """
    if len(ic_series) < 2:
        return 0.0

    recent = ic_series[-window:] if len(ic_series) >= window else ic_series
    if len(recent) < 2:
        return 0.0

    std = float(np.std(recent, ddof=1))
    return std * 10_000.0


def compute_interconnectedness_index(G: nx.DiGraph) -> float:
    """Compute a composite interconnectedness index.

    The index is a weighted composite of three network metrics::

        index = 0.40 * density + 0.35 * clustering + 0.25 * reciprocity

    Where:

    * **density** — fraction of possible edges that are present.
    * **clustering** — average clustering coefficient (undirected view).
    * **reciprocity** — fraction of edges that are mutually reciprocated.

    Parameters
    ----------
    G:
        Directed payment network graph.

    Returns
    -------
    float
        Composite interconnectedness index in the range [0, 1].  Returns
        0.0 for graphs with fewer than 2 nodes.

    Examples
    --------
    >>> import networkx as nx
    >>> G = nx.complete_graph(4, create_using=nx.DiGraph())
    >>> round(compute_interconnectedness_index(G), 4)
    1.0
    """
    if G.number_of_nodes() < 2:
        return 0.0

    density = nx.density(G)

    # Clustering coefficient on undirected projection
    undirected = G.to_undirected()
    clustering = nx.average_clustering(undirected)

    reciprocity = nx.reciprocity(G) if G.number_of_edges() > 0 else 0.0

    return 0.40 * density + 0.35 * clustering + 0.25 * reciprocity


def compute_all_struktur(
    G: nx.DiGraph,
    ic_history: list[float],
) -> dict[str, Any]:
    """Compute all structure indicators in one call.

    Parameters
    ----------
    G:
        Directed payment network graph for the current tick.
    ic_history:
        Historical series of interconnectedness index values (including
        the current tick if already appended).

    Returns
    -------
    dict[str, Any]
        Dictionary with keys:

        * ``average_degree`` — float
        * ``avg_weighted_degree`` — float
        * ``avg_koneksi`` — int
        * ``interconnectedness_index`` — float
        * ``volatility_interconnectedness`` — float

    Examples
    --------
    >>> import networkx as nx
    >>> G = nx.DiGraph()
    >>> G.add_edges_from([(0, 1), (1, 2)])
    >>> result = compute_all_struktur(G, [0.3, 0.32, 0.31])
    >>> set(result.keys()) == {
    ...     'average_degree', 'avg_weighted_degree', 'avg_koneksi',
    ...     'interconnectedness_index', 'volatility_interconnectedness'
    ... }
    True
    """
    ic_index = compute_interconnectedness_index(G)

    # Include current index in history for volatility calculation
    full_history = list(ic_history) + [ic_index]

    return {
        "average_degree": compute_average_degree(G),
        "avg_weighted_degree": compute_avg_weighted_degree(G),
        "avg_koneksi": compute_avg_connections(G),
        "interconnectedness_index": ic_index,
        "volatility_interconnectedness": compute_volatility_interconnectedness(
            full_history
        ),
    }
