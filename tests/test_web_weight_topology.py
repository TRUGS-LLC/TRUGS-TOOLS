"""Tests for trugs_tools.web.weight.topology — query-time node importance."""

from datetime import datetime, timezone, timedelta

import pytest

from trugs_tools.web.weight.topology import (
    NodeTopology,
    compute_topology,
    rank_by_importance,
    find_convergence,
    compute_freshness,
)


# ============================================================================
# Fixtures
# ============================================================================

def _make_graph(name="trug-1", nodes=None, edges=None):
    return {
        "name": name,
        "version": "1.0.0",
        "type": "RESEARCH",
        "nodes": nodes or [],
        "edges": edges or [],
    }


def _edge(from_id, to_id, relation="RELATES_TO", weight=0.5, **extra):
    e = {"from_id": from_id, "to_id": to_id, "relation": relation, "weight": weight}
    e.update(extra)
    return e


# ============================================================================
# NodeTopology dataclass
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testnodetopology AS A RECORD test_suite.
class TestNodeTopology:
    # AGENT SHALL VALIDATE PROCESS test_defaults.
    def test_defaults(self):
        t = NodeTopology(node_id="x")
        assert t.inbound_count == 0
        assert t.weighted_inbound == 0.0
        assert t.sources == set()

    # AGENT SHALL VALIDATE PROCESS test_with_data.
    def test_with_data(self):
        t = NodeTopology(node_id="x", inbound_count=3, weighted_inbound=1.5, sources={"g1", "g2"})
        assert t.inbound_count == 3
        assert len(t.sources) == 2


# ============================================================================
# compute_topology
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testcomputetopology AS A RECORD test_suite.
class TestComputeTopology:
    # AGENT SHALL VALIDATE PROCESS test_empty_graphs.
    def test_empty_graphs(self):
        assert compute_topology([]) == {}
        assert compute_topology([_make_graph()]) == {}

    # AGENT SHALL VALIDATE PROCESS test_single_graph_single_edge.
    def test_single_graph_single_edge(self):
        g = _make_graph(edges=[_edge("a", "b")])
        t = compute_topology([g])
        assert "b" in t
        assert t["b"].inbound_count == 1
        assert t["b"].weighted_inbound == 0.5
        assert "trug-1" in t["b"].sources

    # AGENT SHALL VALIDATE PROCESS test_single_graph_multiple_edges.
    def test_single_graph_multiple_edges(self):
        g = _make_graph(edges=[
            _edge("a", "c", weight=0.3),
            _edge("b", "c", weight=0.7),
        ])
        t = compute_topology([g])
        assert t["c"].inbound_count == 2
        assert abs(t["c"].weighted_inbound - 1.0) < 1e-9

    # AGENT SHALL VALIDATE PROCESS test_multiple_graphs.
    def test_multiple_graphs(self):
        g1 = _make_graph(name="g1", edges=[_edge("a", "x", weight=0.6)])
        g2 = _make_graph(name="g2", edges=[_edge("b", "x", weight=0.4)])
        t = compute_topology([g1, g2])
        assert t["x"].inbound_count == 2
        assert abs(t["x"].weighted_inbound - 1.0) < 1e-9
        assert t["x"].sources == {"g1", "g2"}

    # AGENT SHALL VALIDATE PROCESS test_no_double_count_same_graph.
    def test_no_double_count_same_graph(self):
        g = _make_graph(name="g1", edges=[
            _edge("a", "b", weight=0.3),
            _edge("c", "b", weight=0.4),
        ])
        t = compute_topology([g])
        assert t["b"].inbound_count == 2
        assert t["b"].sources == {"g1"}

    # AGENT SHALL VALIDATE PROCESS test_edge_without_weight_uses_default.
    def test_edge_without_weight_uses_default(self):
        g = _make_graph(edges=[{"from_id": "a", "to_id": "b", "relation": "R"}])
        t = compute_topology([g])
        assert t["b"].weighted_inbound == 0.5

    # AGENT SHALL VALIDATE PROCESS test_edge_without_to_id_ignored.
    def test_edge_without_to_id_ignored(self):
        g = _make_graph(edges=[{"from_id": "a", "to_id": "", "relation": "R"}])
        t = compute_topology([g])
        assert len(t) == 0

    # AGENT SHALL VALIDATE PROCESS test_only_inbound_counted.
    def test_only_inbound_counted(self):
        """from_id is not automatically tracked; only to_id nodes appear."""
        g = _make_graph(edges=[_edge("a", "b")])
        t = compute_topology([g])
        assert "a" not in t
        assert "b" in t


# ============================================================================
# rank_by_importance
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testrankbyimportance AS A RECORD test_suite.
class TestRankByImportance:
    # AGENT SHALL VALIDATE PROCESS test_empty_topology.
    def test_empty_topology(self):
        assert rank_by_importance({}) == []

    # AGENT SHALL VALIDATE PROCESS test_single_node.
    def test_single_node(self):
        t = {"x": NodeTopology("x", inbound_count=2, weighted_inbound=1.2)}
        ranked = rank_by_importance(t)
        assert len(ranked) == 1
        assert ranked[0].node_id == "x"

    # AGENT SHALL VALIDATE PROCESS test_sorted_descending.
    def test_sorted_descending(self):
        t = {
            "a": NodeTopology("a", inbound_count=1, weighted_inbound=0.3),
            "b": NodeTopology("b", inbound_count=2, weighted_inbound=1.0),
            "c": NodeTopology("c", inbound_count=3, weighted_inbound=0.7),
        }
        ranked = rank_by_importance(t)
        assert [r.node_id for r in ranked] == ["b", "c", "a"]

    # AGENT SHALL VALIDATE PROCESS test_min_inbound_filter.
    def test_min_inbound_filter(self):
        t = {
            "a": NodeTopology("a", inbound_count=1, weighted_inbound=0.3),
            "b": NodeTopology("b", inbound_count=3, weighted_inbound=1.0),
        }
        ranked = rank_by_importance(t, min_inbound=2)
        assert len(ranked) == 1
        assert ranked[0].node_id == "b"

    # AGENT SHALL VALIDATE PROCESS test_min_inbound_zero.
    def test_min_inbound_zero(self):
        t = {
            "a": NodeTopology("a", inbound_count=0, weighted_inbound=0.0),
            "b": NodeTopology("b", inbound_count=1, weighted_inbound=0.5),
        }
        ranked = rank_by_importance(t, min_inbound=0)
        assert len(ranked) == 2


# ============================================================================
# find_convergence
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testfindconvergence AS A RECORD test_suite.
class TestFindConvergence:
    # AGENT SHALL VALIDATE PROCESS test_empty_topology.
    def test_empty_topology(self):
        assert find_convergence({}) == []

    # AGENT SHALL VALIDATE PROCESS test_no_convergence.
    def test_no_convergence(self):
        t = {"a": NodeTopology("a", sources={"g1"})}
        assert find_convergence(t, min_sources=2) == []

    # AGENT SHALL VALIDATE PROCESS test_convergence_detected.
    def test_convergence_detected(self):
        t = {
            "a": NodeTopology("a", inbound_count=2, weighted_inbound=1.0, sources={"g1", "g2"}),
            "b": NodeTopology("b", inbound_count=1, weighted_inbound=0.5, sources={"g1"}),
        }
        converged = find_convergence(t, min_sources=2)
        assert len(converged) == 1
        assert converged[0].node_id == "a"

    # AGENT SHALL VALIDATE PROCESS test_convergence_sorted_by_sources.
    def test_convergence_sorted_by_sources(self):
        t = {
            "a": NodeTopology("a", inbound_count=2, weighted_inbound=0.8, sources={"g1", "g2"}),
            "b": NodeTopology("b", inbound_count=3, weighted_inbound=1.5, sources={"g1", "g2", "g3"}),
        }
        converged = find_convergence(t, min_sources=2)
        assert converged[0].node_id == "b"
        assert converged[1].node_id == "a"

    # AGENT SHALL VALIDATE PROCESS test_convergence_integration_with_compute_topology.
    def test_convergence_integration_with_compute_topology(self):
        g1 = _make_graph(name="g1", edges=[_edge("a", "x", weight=0.6)])
        g2 = _make_graph(name="g2", edges=[_edge("b", "x", weight=0.4)])
        g3 = _make_graph(name="g3", edges=[_edge("c", "y", weight=0.3)])
        t = compute_topology([g1, g2, g3])
        converged = find_convergence(t, min_sources=2)
        assert len(converged) == 1
        assert converged[0].node_id == "x"


# ============================================================================
# compute_freshness
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testcomputefreshness AS A RECORD test_suite.
class TestComputeFreshness:
    # AGENT SHALL VALIDATE PROCESS test_no_timestamp.
    def test_no_timestamp(self):
        assert compute_freshness({}) == 0.0

    # AGENT SHALL VALIDATE PROCESS test_fresh_edge.
    def test_fresh_edge(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        edge = {"timestamp": "2026-01-01T00:00:00+00:00"}
        f = compute_freshness(edge, now=now)
        assert abs(f - 1.0) < 0.01

    # AGENT SHALL VALIDATE PROCESS test_30_day_old_edge.
    def test_30_day_old_edge(self):
        now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        edge = {"timestamp": "2026-01-02T00:00:00+00:00"}
        f = compute_freshness(edge, now=now)
        assert 0.45 < f < 0.55  # ~half-life

    # AGENT SHALL VALIDATE PROCESS test_very_old_edge.
    def test_very_old_edge(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        edge = {"timestamp": "2024-01-01T00:00:00+00:00"}
        f = compute_freshness(edge, now=now)
        assert f < 0.01

    # AGENT SHALL VALIDATE PROCESS test_future_timestamp.
    def test_future_timestamp(self):
        """Future timestamps should return 1.0 (clamped, age=0)."""
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        edge = {"timestamp": "2027-01-01T00:00:00+00:00"}
        f = compute_freshness(edge, now=now)
        assert abs(f - 1.0) < 0.01

    # AGENT SHALL VALIDATE PROCESS test_created_field.
    def test_created_field(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        edge = {"created": "2026-01-01T00:00:00+00:00"}
        f = compute_freshness(edge, now=now)
        assert f > 0.9

    # AGENT SHALL VALIDATE PROCESS test_nested_properties_timestamp.
    def test_nested_properties_timestamp(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        edge = {"properties": {"timestamp": "2026-01-01T00:00:00+00:00"}}
        f = compute_freshness(edge, now=now)
        assert f > 0.9

    # AGENT SHALL VALIDATE PROCESS test_invalid_timestamp.
    def test_invalid_timestamp(self):
        assert compute_freshness({"timestamp": "not-a-date"}) == 0.0

    # AGENT SHALL VALIDATE PROCESS test_custom_half_life.
    def test_custom_half_life(self):
        now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        edge = {"timestamp": "2026-01-01T00:00:00+00:00"}
        # 30 days old with 15-day half-life → ~0.25
        f = compute_freshness(edge, now=now, half_life_days=15.0)
        assert 0.2 < f < 0.3

    # AGENT SHALL VALIDATE PROCESS test_naive_timestamp_treated_as_utc.
    def test_naive_timestamp_treated_as_utc(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        edge = {"timestamp": "2026-01-01T00:00:00"}
        f = compute_freshness(edge, now=now)
        assert f > 0.9

    # AGENT SHALL VALIDATE PROCESS test_return_bounded_zero_one.
    def test_return_bounded_zero_one(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        edge = {"timestamp": "2026-01-01T00:00:00+00:00"}
        f = compute_freshness(edge, now=now)
        assert 0.0 <= f <= 1.0
