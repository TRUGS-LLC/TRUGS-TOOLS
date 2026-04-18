"""Tests for trugs_tools.web.refresh.diff — TRUG diff computation and application."""

import copy

import pytest

from trugs_tools.web.refresh.diff import TrugDiff, diff_trugs, apply_diff


# ============================================================================
# Fixtures
# ============================================================================

def _make_graph(name="test", nodes=None, edges=None):
    """Build a minimal TRUG graph dict for testing."""
    return {
        "name": name,
        "version": "1.0.0",
        "type": "RESEARCH",
        "nodes": nodes or [],
        "edges": edges or [],
    }


def _node(nid, ntype="CONCEPT", name=None, **props):
    base_props = {"name": name or nid, **props}
    return {
        "id": nid,
        "type": ntype,
        "properties": base_props,
        "metric_level": "BASE",
        "parent_id": None,
        "contains": [],
        "dimension": "web_structure",
    }


def _edge(from_id, to_id, relation="RELATES_TO", weight=None):
    e = {"from_id": from_id, "to_id": to_id, "relation": relation}
    if weight is not None:
        e["weight"] = weight
    return e


# ============================================================================
# TrugDiff dataclass
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testtrugdiff AS A RECORD test_suite.
class TestTrugDiff:
    # AGENT SHALL VALIDATE PROCESS test_empty_diff.
    def test_empty_diff(self):
        d = TrugDiff()
        assert d.is_empty
        assert d.summary == "no changes"

    # AGENT SHALL VALIDATE PROCESS test_non_empty_diff.
    def test_non_empty_diff(self):
        d = TrugDiff(nodes_added=[{"id": "a"}])
        assert not d.is_empty
        assert "+1 nodes" in d.summary

    # AGENT SHALL VALIDATE PROCESS test_full_summary.
    def test_full_summary(self):
        d = TrugDiff(
            nodes_added=[1],
            nodes_removed=[2, 3],
            nodes_modified=[4],
            edges_added=[5],
            edges_removed=[6, 7, 8],
            edges_reweighted=[9],
        )
        s = d.summary
        assert "+1 nodes" in s
        assert "-2 nodes" in s
        assert "~1 nodes" in s
        assert "+1 edges" in s
        assert "-3 edges" in s
        assert "~1 edges" in s


# ============================================================================
# diff_trugs — node diffs
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testdifftrugsnodes AS A RECORD test_suite.
class TestDiffTrugsNodes:
    # AGENT SHALL VALIDATE PROCESS test_identical_graphs.
    def test_identical_graphs(self):
        g = _make_graph(nodes=[_node("a"), _node("b")])
        d = diff_trugs(g, copy.deepcopy(g))
        assert d.is_empty

    # AGENT SHALL VALIDATE PROCESS test_node_added.
    def test_node_added(self):
        old = _make_graph(nodes=[_node("a")])
        new = _make_graph(nodes=[_node("a"), _node("b")])
        d = diff_trugs(old, new)
        assert len(d.nodes_added) == 1
        assert d.nodes_added[0]["id"] == "b"
        assert not d.nodes_removed
        assert not d.nodes_modified

    # AGENT SHALL VALIDATE PROCESS test_node_removed.
    def test_node_removed(self):
        old = _make_graph(nodes=[_node("a"), _node("b")])
        new = _make_graph(nodes=[_node("a")])
        d = diff_trugs(old, new)
        assert len(d.nodes_removed) == 1
        assert d.nodes_removed[0]["id"] == "b"

    # AGENT SHALL VALIDATE PROCESS test_node_modified_type_change.
    def test_node_modified_type_change(self):
        old = _make_graph(nodes=[_node("a", ntype="CONCEPT")])
        new = _make_graph(nodes=[_node("a", ntype="PERSON")])
        d = diff_trugs(old, new)
        assert len(d.nodes_modified) == 1
        assert d.nodes_modified[0]["id"] == "a"
        assert d.nodes_modified[0]["old"]["type"] == "CONCEPT"
        assert d.nodes_modified[0]["new"]["type"] == "PERSON"

    # AGENT SHALL VALIDATE PROCESS test_node_modified_properties_change.
    def test_node_modified_properties_change(self):
        n1 = _node("a", name="Alpha")
        n2 = _node("a", name="Alpha Updated")
        d = diff_trugs(_make_graph(nodes=[n1]), _make_graph(nodes=[n2]))
        assert len(d.nodes_modified) == 1
        assert d.nodes_modified[0]["id"] == "a"
        assert d.nodes_modified[0]["old"]["properties"]["name"] == "Alpha"
        assert d.nodes_modified[0]["new"]["properties"]["name"] == "Alpha Updated"

    # AGENT SHALL VALIDATE PROCESS test_node_modified_metric_level_change.
    def test_node_modified_metric_level_change(self):
        n1 = _node("a")
        n2 = copy.deepcopy(n1)
        n2["metric_level"] = "ADVANCED"
        d = diff_trugs(_make_graph(nodes=[n1]), _make_graph(nodes=[n2]))
        assert len(d.nodes_modified) == 1
        assert d.nodes_modified[0]["id"] == "a"
        assert d.nodes_modified[0]["old"]["metric_level"] == "BASE"
        assert d.nodes_modified[0]["new"]["metric_level"] == "ADVANCED"

    # AGENT SHALL VALIDATE PROCESS test_empty_to_populated.
    def test_empty_to_populated(self):
        d = diff_trugs(_make_graph(), _make_graph(nodes=[_node("x")]))
        assert len(d.nodes_added) == 1

    # AGENT SHALL VALIDATE PROCESS test_populated_to_empty.
    def test_populated_to_empty(self):
        d = diff_trugs(_make_graph(nodes=[_node("x")]), _make_graph())
        assert len(d.nodes_removed) == 1

    # AGENT SHALL VALIDATE PROCESS test_both_empty.
    def test_both_empty(self):
        d = diff_trugs(_make_graph(), _make_graph())
        assert d.is_empty

    # AGENT SHALL VALIDATE PROCESS test_multiple_additions_and_removals.
    def test_multiple_additions_and_removals(self):
        old = _make_graph(nodes=[_node("a"), _node("b")])
        new = _make_graph(nodes=[_node("b"), _node("c"), _node("d")])
        d = diff_trugs(old, new)
        assert len(d.nodes_added) == 2
        assert len(d.nodes_removed) == 1
        added_ids = {n["id"] for n in d.nodes_added}
        assert added_ids == {"c", "d"}
        assert d.nodes_removed[0]["id"] == "a"


# ============================================================================
# diff_trugs — edge diffs
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testdifftrugsedges AS A RECORD test_suite.
class TestDiffTrugsEdges:
    # AGENT SHALL VALIDATE PROCESS test_edge_added.
    def test_edge_added(self):
        old = _make_graph(edges=[])
        new = _make_graph(edges=[_edge("a", "b")])
        d = diff_trugs(old, new)
        assert len(d.edges_added) == 1

    # AGENT SHALL VALIDATE PROCESS test_edge_removed.
    def test_edge_removed(self):
        old = _make_graph(edges=[_edge("a", "b")])
        new = _make_graph(edges=[])
        d = diff_trugs(old, new)
        assert len(d.edges_removed) == 1

    # AGENT SHALL VALIDATE PROCESS test_edge_reweighted.
    def test_edge_reweighted(self):
        old = _make_graph(edges=[_edge("a", "b", weight=0.3)])
        new = _make_graph(edges=[_edge("a", "b", weight=0.8)])
        d = diff_trugs(old, new)
        assert not d.edges_added
        assert not d.edges_removed
        assert len(d.edges_reweighted) == 1
        assert d.edges_reweighted[0]["old_weight"] == 0.3
        assert d.edges_reweighted[0]["new_weight"] == 0.8

    # AGENT SHALL VALIDATE PROCESS test_edge_reweight_below_threshold.
    def test_edge_reweight_below_threshold(self):
        old = _make_graph(edges=[_edge("a", "b", weight=0.30)])
        new = _make_graph(edges=[_edge("a", "b", weight=0.33)])
        d = diff_trugs(old, new, weight_threshold=0.05)
        assert len(d.edges_reweighted) == 0

    # AGENT SHALL VALIDATE PROCESS test_edge_reweight_custom_threshold.
    def test_edge_reweight_custom_threshold(self):
        old = _make_graph(edges=[_edge("a", "b", weight=0.30)])
        new = _make_graph(edges=[_edge("a", "b", weight=0.33)])
        d = diff_trugs(old, new, weight_threshold=0.02)
        assert len(d.edges_reweighted) == 1

    # AGENT SHALL VALIDATE PROCESS test_edge_no_weight_no_reweight.
    def test_edge_no_weight_no_reweight(self):
        """Edges without weights are not considered reweighted."""
        old = _make_graph(edges=[_edge("a", "b")])
        new = _make_graph(edges=[_edge("a", "b")])
        d = diff_trugs(old, new)
        assert d.is_empty

    # AGENT SHALL VALIDATE PROCESS test_edge_matching_by_tuple.
    def test_edge_matching_by_tuple(self):
        """Same endpoints, different relation → different edges."""
        old = _make_graph(edges=[_edge("a", "b", "CITES")])
        new = _make_graph(edges=[_edge("a", "b", "MENTIONS")])
        d = diff_trugs(old, new)
        assert len(d.edges_added) == 1
        assert len(d.edges_removed) == 1

    # AGENT SHALL VALIDATE PROCESS test_mixed_edge_changes.
    def test_mixed_edge_changes(self):
        old = _make_graph(edges=[
            _edge("a", "b", weight=0.5),
            _edge("b", "c", weight=0.3),
        ])
        new = _make_graph(edges=[
            _edge("a", "b", weight=0.9),
            _edge("c", "d", weight=0.7),
        ])
        d = diff_trugs(old, new)
        assert len(d.edges_added) == 1
        assert len(d.edges_removed) == 1
        assert len(d.edges_reweighted) == 1


# ============================================================================
# apply_diff
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testapplydiff AS A RECORD test_suite.
class TestApplyDiff:
    # AGENT SHALL VALIDATE PROCESS test_apply_empty_diff.
    def test_apply_empty_diff(self):
        g = _make_graph(nodes=[_node("a")], edges=[_edge("a", "b")])
        result = apply_diff(g, TrugDiff())
        assert result == g

    # AGENT SHALL VALIDATE PROCESS test_apply_does_not_mutate_input.
    def test_apply_does_not_mutate_input(self):
        g = _make_graph(nodes=[_node("a")])
        original = copy.deepcopy(g)
        diff = TrugDiff(nodes_added=[_node("b")])
        apply_diff(g, diff)
        assert g == original

    # AGENT SHALL VALIDATE PROCESS test_apply_node_addition.
    def test_apply_node_addition(self):
        g = _make_graph(nodes=[_node("a")])
        diff = TrugDiff(nodes_added=[_node("b")])
        result = apply_diff(g, diff)
        ids = {n["id"] for n in result["nodes"]}
        assert ids == {"a", "b"}

    # AGENT SHALL VALIDATE PROCESS test_apply_node_removal.
    def test_apply_node_removal(self):
        g = _make_graph(nodes=[_node("a"), _node("b")])
        diff = TrugDiff(nodes_removed=[_node("b")])
        result = apply_diff(g, diff)
        ids = {n["id"] for n in result["nodes"]}
        assert ids == {"a"}

    # AGENT SHALL VALIDATE PROCESS test_apply_node_modification.
    def test_apply_node_modification(self):
        old_n = _node("a", name="Alpha")
        new_n = _node("a", name="Alpha Updated")
        g = _make_graph(nodes=[old_n])
        diff = TrugDiff(nodes_modified=[{"id": "a", "old": old_n, "new": new_n}])
        result = apply_diff(g, diff)
        assert result["nodes"][0]["properties"]["name"] == "Alpha Updated"

    # AGENT SHALL VALIDATE PROCESS test_apply_edge_addition.
    def test_apply_edge_addition(self):
        g = _make_graph(edges=[])
        diff = TrugDiff(edges_added=[_edge("a", "b")])
        result = apply_diff(g, diff)
        assert len(result["edges"]) == 1

    # AGENT SHALL VALIDATE PROCESS test_apply_edge_removal.
    def test_apply_edge_removal(self):
        g = _make_graph(edges=[_edge("a", "b"), _edge("b", "c")])
        diff = TrugDiff(edges_removed=[_edge("a", "b")])
        result = apply_diff(g, diff)
        assert len(result["edges"]) == 1
        assert result["edges"][0]["from_id"] == "b"

    # AGENT SHALL VALIDATE PROCESS test_apply_edge_reweight.
    def test_apply_edge_reweight(self):
        g = _make_graph(edges=[_edge("a", "b", weight=0.3)])
        diff = TrugDiff(edges_reweighted=[{
            "edge": _edge("a", "b", weight=0.8),
            "old_weight": 0.3,
            "new_weight": 0.8,
        }])
        result = apply_diff(g, diff)
        assert result["edges"][0]["weight"] == 0.8

    # AGENT SHALL VALIDATE PROCESS test_roundtrip_diff_apply.
    def test_roundtrip_diff_apply(self):
        """diff → apply should produce the new graph."""
        old = _make_graph(
            nodes=[_node("a"), _node("b")],
            edges=[_edge("a", "b", weight=0.5)],
        )
        new = _make_graph(
            nodes=[_node("a"), _node("c")],
            edges=[_edge("a", "c", weight=0.7)],
        )
        d = diff_trugs(old, new)
        result = apply_diff(old, d)
        result_ids = {n["id"] for n in result["nodes"]}
        assert result_ids == {"a", "c"}
        assert len(result["edges"]) == 1
        assert result["edges"][0]["to_id"] == "c"
        assert result["edges"][0]["weight"] == 0.7

    # AGENT SHALL VALIDATE PROCESS test_apply_duplicate_node_add.
    def test_apply_duplicate_node_add(self):
        """Adding a node that already exists should not duplicate it."""
        g = _make_graph(nodes=[_node("a")])
        diff = TrugDiff(nodes_added=[_node("a")])
        result = apply_diff(g, diff)
        assert len(result["nodes"]) == 1

    # AGENT SHALL VALIDATE PROCESS test_apply_duplicate_edge_add.
    def test_apply_duplicate_edge_add(self):
        """Adding an edge that already exists should not duplicate it."""
        g = _make_graph(edges=[_edge("a", "b")])
        diff = TrugDiff(edges_added=[_edge("a", "b")])
        result = apply_diff(g, diff)
        assert len(result["edges"]) == 1
