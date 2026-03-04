"""Tests for indicator computation engine."""
import pytest
import networkx as nx
import numpy as np
from fmi_sim.indicators.thresholds import ThresholdClassifier, DEFAULT_THRESHOLDS
from fmi_sim.indicators.velositas import (
    compute_tor, compute_tor_adjusted, compute_queue_ratio, compute_throughput_zona3
)
from fmi_sim.indicators.struktur import (
    compute_average_degree, compute_avg_weighted_degree, compute_avg_connections,
    compute_volatility_interconnectedness, compute_interconnectedness_index,
)
from fmi_sim.indicators.infrastruktur import (
    compute_system_utilization, compute_system_availability,
)


class TestThresholdClassifier:
    def test_tor_normal(self):
        # TOR < 1.36 → normal
        result = ThresholdClassifier.classify("tor", 1.0)
        assert result == "normal"

    def test_tor_waspada(self):
        # 1.36 ≤ TOR < 2.19 → waspada
        result = ThresholdClassifier.classify("tor", 1.80)
        assert result == "waspada"

    def test_tor_siaga(self):
        # 2.19 ≤ TOR < 3.03 → siaga
        result = ThresholdClassifier.classify("tor", 2.50)
        assert result == "siaga"

    def test_tor_krisis(self):
        # TOR ≥ 3.03 → krisis
        result = ThresholdClassifier.classify("tor", 3.50)
        assert result == "krisis"

    def test_avg_degree_normal(self):
        # AD > 65.80 → normal
        result = ThresholdClassifier.classify("average_degree", 74.0)
        assert result == "normal"

    def test_avg_degree_waspada(self):
        # 63.18 < AD ≤ 65.80 → waspada
        result = ThresholdClassifier.classify("average_degree", 64.0)
        assert result == "waspada"

    def test_avg_degree_siaga(self):
        # 60.55 < AD ≤ 63.18 → siaga
        result = ThresholdClassifier.classify("average_degree", 61.5)
        assert result == "siaga"

    def test_avg_degree_krisis(self):
        # AD ≤ 60.55 → krisis
        result = ThresholdClassifier.classify("average_degree", 59.0)
        assert result == "krisis"

    def test_unknown_indicator_returns_normal(self):
        result = ThresholdClassifier.classify("nonexistent_indicator", 999.0)
        assert result == "normal"

    def test_all_known_indicators_present(self):
        expected = [
            "tor", "average_degree", "system_availability", "queue_ratio",
            "awd", "avg_koneksi", "volatility_interconnectedness",
            "system_utilization", "unsettled_banks",
        ]
        for ind in expected:
            assert ind in DEFAULT_THRESHOLDS, f"Missing threshold for {ind}"


class TestVelositas:
    def test_tor_basic(self):
        tor = compute_tor(settled_value=100.0, opening_balance=60.0, closing_balance=40.0)
        assert tor == pytest.approx(2.0)  # 100 / ((60+40)/2)

    def test_tor_zero_balance(self):
        tor = compute_tor(settled_value=100.0, opening_balance=0.0, closing_balance=0.0)
        # Should handle division by zero gracefully
        assert tor == float("inf") or tor > 0

    def test_tor_adjusted(self):
        tor_adj = compute_tor_adjusted(tor=2.0, adjustment_factor=0.85)
        assert tor_adj == pytest.approx(1.70)

    def test_queue_ratio(self):
        qr = compute_queue_ratio(peak_queued_value=100.0, total_submitted_value=500.0)
        assert 0 <= qr <= 100

    def test_throughput_zona3(self):
        tp = compute_throughput_zona3(zona3_value=300.0, total_value=1000.0)
        assert tp == pytest.approx(30.0)

    def test_throughput_zona3_zero_total(self):
        tp = compute_throughput_zona3(zona3_value=0.0, total_value=0.0)
        assert tp == 0.0


class TestStruktur:
    @pytest.fixture
    def sample_graph(self):
        G = nx.DiGraph()
        G.add_nodes_from(range(5))
        edges = [(0, 1, 100), (0, 2, 200), (1, 2, 150), (2, 3, 300),
                 (3, 4, 250), (4, 0, 180), (1, 3, 120), (2, 4, 90)]
        G.add_weighted_edges_from(edges)
        return G

    def test_average_degree(self, sample_graph):
        ad = compute_average_degree(sample_graph)
        assert ad == pytest.approx(8 / 5)  # 8 edges / 5 nodes = 1.6

    def test_avg_weighted_degree(self, sample_graph):
        awd = compute_avg_weighted_degree(sample_graph)
        assert awd > 0

    def test_avg_connections(self, sample_graph):
        avg_c = compute_avg_connections(sample_graph)
        assert avg_c > 0

    def test_interconnectedness_index(self, sample_graph):
        ic = compute_interconnectedness_index(sample_graph)
        assert 0 <= ic <= 1

    def test_volatility_ic(self):
        series = list(range(25))  # 25 values
        vol = compute_volatility_interconnectedness(series, window=20)
        assert vol >= 0


class TestInfrastruktur:
    def test_system_utilization(self):
        su = compute_system_utilization(actual_load=50000, max_capacity=200000)
        assert su == pytest.approx(25.0)

    def test_system_availability(self):
        avail = compute_system_availability(uptime_minutes=9900, total_minutes=10000)
        assert avail == pytest.approx(99.0)

    def test_system_availability_full(self):
        avail = compute_system_availability(uptime_minutes=600, total_minutes=600)
        assert avail == pytest.approx(100.0)
