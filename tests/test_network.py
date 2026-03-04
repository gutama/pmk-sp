"""Tests for PaymentNetwork generation and topology."""
import pytest
import networkx as nx
from fmi_sim.core.network import PaymentNetwork, NetworkParams


@pytest.fixture
def rtgs_network():
    net = PaymentNetwork(n_banks=50, network_type="rtgs")
    params = NetworkParams(
        n_core_banks=7,
        n_periphery=43,
        target_avg_degree=74.0,
        weight_distribution={"type": "lognormal", "mu": 10.0, "sigma": 2.5},
    )
    return net.generate_topology(params)


def test_network_creation(rtgs_network):
    G = rtgs_network
    assert isinstance(G, nx.DiGraph)
    assert G.number_of_nodes() > 0


def test_network_node_count(rtgs_network):
    G = rtgs_network
    assert G.number_of_nodes() == 50


def test_network_has_edges(rtgs_network):
    G = rtgs_network
    assert G.number_of_edges() > 0


def test_network_avg_degree_reasonable(rtgs_network):
    G = rtgs_network
    ad = G.number_of_edges() / G.number_of_nodes()
    # For n=50, AD should be reasonable (network is connected)
    assert ad > 0
    assert ad < G.number_of_nodes()


def test_network_weights_positive(rtgs_network):
    G = rtgs_network
    for u, v, d in G.edges(data=True):
        assert d.get("weight", 0) > 0, f"Edge ({u},{v}) has non-positive weight"


def test_network_stats():
    net = PaymentNetwork(n_banks=30, network_type="rtgs")
    params = NetworkParams(
        n_core_banks=5,
        n_periphery=25,
        target_avg_degree=20.0,
        weight_distribution={"type": "lognormal", "mu": 10.0, "sigma": 2.0},
    )
    G = net.generate_topology(params)
    stats = PaymentNetwork.get_network_stats(G)
    assert "average_degree" in stats
    assert "density" in stats
    assert stats["average_degree"] >= 0


def test_different_systems():
    for system in ["rtgs", "fast", "raja"]:
        net = PaymentNetwork(n_banks=20, network_type=system)
        params = NetworkParams(
            n_core_banks=3,
            n_periphery=17,
            target_avg_degree=10.0,
            weight_distribution={"type": "lognormal", "mu": 9.0, "sigma": 2.0},
        )
        G = net.generate_topology(params)
        assert G.number_of_nodes() == 20
