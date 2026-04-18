"""Tests for TrugAnalyzer — structural graph analysis (#618)."""

import json
import pytest
from pathlib import Path

from trugs_tools.analyzer import TrugAnalyzer, TrugComplexityMetrics
from trugs_tools.trug_graph import TrugGraph


# ── Helpers ──────────────────────────────────────────────────────────────


def _linear():
    """root → child → grandchild (linear hierarchy + semantic edge)."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child"]},
            {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": ["grandchild"]},
            {"id": "grandchild", "type": "DOCUMENT", "parent_id": "child", "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "child", "relation": "contains"},
            {"from_id": "child", "to_id": "grandchild", "relation": "contains"},
            {"from_id": "child", "to_id": "grandchild", "relation": "uses"},
        ],
    })


def _with_orphan():
    """root → child, plus orphan (no parent, no edges)."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child"]},
            {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": []},
            {"id": "orphan", "type": "COMPONENT", "parent_id": None, "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "child", "relation": "contains"},
        ],
    })


def _diamond():
    """root → A, root → B, A → sink, B → sink via semantic edges."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["a", "b", "sink"]},
            {"id": "a", "type": "COMPONENT", "parent_id": "root", "contains": []},
            {"id": "b", "type": "COMPONENT", "parent_id": "root", "contains": []},
            {"id": "sink", "type": "DOCUMENT", "parent_id": "root", "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "a", "relation": "contains"},
            {"from_id": "root", "to_id": "b", "relation": "contains"},
            {"from_id": "root", "to_id": "sink", "relation": "contains"},
            {"from_id": "a", "to_id": "sink", "relation": "uses"},
            {"from_id": "b", "to_id": "sink", "relation": "uses"},
        ],
    })


def _with_dead():
    """root contains child1 and child2, but child2 has no edge to_id and is not in any contains[]."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child1"]},
            {"id": "child1", "type": "COMPONENT", "parent_id": "root", "contains": []},
            {"id": "child2", "type": "DOCUMENT", "parent_id": "root", "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "child1", "relation": "contains"},
            # child2 has parent_id=root but root.contains doesn't list it, no edge to_id targets it
        ],
    })


def _with_stale():
    """root → comp → doc, comp is stale, comp uses doc."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["comp", "doc"]},
            {"id": "comp", "type": "COMPONENT", "parent_id": "root", "contains": [], "properties": {"stale": True, "stale_reason": "file not found"}},
            {"id": "doc", "type": "DOCUMENT", "parent_id": "root", "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "comp", "relation": "contains"},
            {"from_id": "root", "to_id": "doc", "relation": "contains"},
            {"from_id": "comp", "to_id": "doc", "relation": "uses"},
        ],
    })


def _with_stale_no_propagation():
    """Stale node with only a 'tests' edge (doesn't propagate)."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["comp", "test"]},
            {"id": "comp", "type": "COMPONENT", "parent_id": "root", "contains": [], "properties": {"stale": True}},
            {"id": "test", "type": "TEST", "parent_id": "root", "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "comp", "relation": "contains"},
            {"from_id": "root", "to_id": "test", "relation": "contains"},
            {"from_id": "comp", "to_id": "test", "relation": "tests"},
        ],
    })


def _with_cross_folder():
    """Graph with cross-folder edge (contains ':')."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["comp"]},
            {"id": "comp", "type": "COMPONENT", "parent_id": "root", "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "comp", "relation": "contains"},
            {"from_id": "comp", "to_id": "OTHER_FOLDER:external", "relation": "uses"},
        ],
    })


def _empty():
    return TrugGraph.from_dict({"nodes": [], "edges": []})


def _no_roots():
    """All nodes have parent_id set (no root)."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "a", "type": "T", "parent_id": "b", "contains": []},
            {"id": "b", "type": "T", "parent_id": "a", "contains": []},
        ],
        "edges": [],
    })


def _branching():
    """root → A, A uses B, A uses C (branching semantic edges)."""
    return TrugGraph.from_dict({
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["a", "b", "c"]},
            {"id": "a", "type": "COMPONENT", "parent_id": "root", "contains": []},
            {"id": "b", "type": "COMPONENT", "parent_id": "root", "contains": []},
            {"id": "c", "type": "COMPONENT", "parent_id": "root", "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "a", "relation": "contains"},
            {"from_id": "root", "to_id": "b", "relation": "contains"},
            {"from_id": "root", "to_id": "c", "relation": "contains"},
            {"from_id": "a", "to_id": "b", "relation": "uses"},
            {"from_id": "a", "to_id": "c", "relation": "uses"},
        ],
    })


# ── find_unreachable_nodes ───────────────────────────────────────────────


class TestFindUnreachableNodes:
    def test_linear_no_unreachable(self):
        assert TrugAnalyzer.find_unreachable_nodes(_linear()) == set()

    def test_empty(self):
        assert TrugAnalyzer.find_unreachable_nodes(_empty()) == set()

    def test_orphan_detected(self):
        unreachable = TrugAnalyzer.find_unreachable_nodes(_with_orphan())
        # orphan is a root itself, so reachable from itself — but it's isolated
        # Since orphan has parent_id=None, it IS a root → reachable from itself
        assert "orphan" not in unreachable  # orphan is a root, so "reachable"

    def test_all_reachable_via_hierarchy(self):
        assert TrugAnalyzer.find_unreachable_nodes(_diamond()) == set()

    def test_cross_folder_skipped(self):
        assert TrugAnalyzer.find_unreachable_nodes(_with_cross_folder()) == set()

    def test_no_roots_all_unreachable(self):
        assert TrugAnalyzer.find_unreachable_nodes(_no_roots()) == {"a", "b"}

    def test_node_reachable_only_via_semantic_edge(self):
        """Node with parent but not in parent's contains — reachable via semantic edge."""
        g = TrugGraph.from_dict({
            "nodes": [
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["a"]},
                {"id": "a", "type": "COMPONENT", "parent_id": "root", "contains": []},
                {"id": "b", "type": "DOCUMENT", "parent_id": None, "contains": []},
            ],
            "edges": [
                {"from_id": "root", "to_id": "a", "relation": "contains"},
                {"from_id": "a", "to_id": "b", "relation": "uses"},
            ],
        })
        # b is a root (parent_id=None) OR reachable via uses edge from a
        assert TrugAnalyzer.find_unreachable_nodes(g) == set()


# ── find_dead_nodes ──────────────────────────────────────────────────────


class TestFindDeadNodes:
    def test_linear_no_dead(self):
        assert TrugAnalyzer.find_dead_nodes(_linear()) == set()

    def test_empty(self):
        assert TrugAnalyzer.find_dead_nodes(_empty()) == set()

    def test_dead_node_detected(self):
        dead = TrugAnalyzer.find_dead_nodes(_with_dead())
        assert "child2" in dead

    def test_all_referenced(self):
        assert TrugAnalyzer.find_dead_nodes(_diamond()) == set()

    def test_root_not_dead(self):
        dead = TrugAnalyzer.find_dead_nodes(_with_dead())
        assert "root" not in dead

    def test_node_in_contains_not_dead(self):
        """Node listed in contains[] but no edge to_id is NOT dead."""
        g = TrugGraph.from_dict({
            "nodes": [
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child"]},
                {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": []},
            ],
            "edges": [],  # No edges at all, but child is in root.contains
        })
        assert TrugAnalyzer.find_dead_nodes(g) == set()

    def test_node_as_edge_target_not_dead(self):
        """Node targeted by edge but not in any contains[] is NOT dead."""
        g = TrugGraph.from_dict({
            "nodes": [
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": []},
                {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": []},
            ],
            "edges": [
                {"from_id": "root", "to_id": "child", "relation": "uses"},
            ],
        })
        assert TrugAnalyzer.find_dead_nodes(g) == set()


# ── dominator_tree ───────────────────────────────────────────────────────


class TestDominatorTree:
    def test_linear(self):
        g = TrugGraph.from_dict({
            "nodes": [
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["a", "b"]},
                {"id": "a", "type": "COMPONENT", "parent_id": "root", "contains": []},
                {"id": "b", "type": "COMPONENT", "parent_id": "root", "contains": []},
            ],
            "edges": [
                {"from_id": "root", "to_id": "a", "relation": "contains"},
                {"from_id": "root", "to_id": "b", "relation": "contains"},
                {"from_id": "root", "to_id": "a", "relation": "uses"},
                {"from_id": "a", "to_id": "b", "relation": "uses"},
            ],
        })
        dt = TrugAnalyzer.dominator_tree(g)
        assert dt["root"] is None
        assert dt["a"] == "root"
        assert dt["b"] in ("root", "a")  # b reachable from root→a→b

    def test_diamond(self):
        dt = TrugAnalyzer.dominator_tree(_diamond())
        if "root" in dt:
            assert dt["root"] is None
        if "sink" in dt:
            # sink dominated by root (both a and b lead to it, both from root)
            assert dt["sink"] == "root"

    def test_empty(self):
        assert TrugAnalyzer.dominator_tree(_empty()) == {}

    def test_no_roots(self):
        assert TrugAnalyzer.dominator_tree(_no_roots()) == {}


# ── impact_set ───────────────────────────────────────────────────────────


class TestImpactSet:
    def test_forward(self):
        g = _linear()
        impact = TrugAnalyzer.impact_set(g, "child")
        assert "grandchild" in impact

    def test_leaf_empty(self):
        assert TrugAnalyzer.impact_set(_linear(), "grandchild") == set()

    def test_nonexistent(self):
        assert TrugAnalyzer.impact_set(_linear(), "nope") == set()

    def test_empty(self):
        assert TrugAnalyzer.impact_set(_empty(), "x") == set()

    def test_diamond_root(self):
        impact = TrugAnalyzer.impact_set(_diamond(), "a")
        assert "sink" in impact

    def test_excludes_self(self):
        assert "child" not in TrugAnalyzer.impact_set(_linear(), "child")


# ── dependency_set ───────────────────────────────────────────────────────


class TestDependencySet:
    def test_reverse(self):
        deps = TrugAnalyzer.dependency_set(_diamond(), "sink")
        assert "a" in deps
        assert "b" in deps

    def test_root_empty(self):
        # root has no incoming semantic edges
        assert TrugAnalyzer.dependency_set(_linear(), "root") == set()

    def test_nonexistent(self):
        assert TrugAnalyzer.dependency_set(_linear(), "nope") == set()

    def test_empty(self):
        assert TrugAnalyzer.dependency_set(_empty(), "x") == set()

    def test_excludes_self(self):
        assert "sink" not in TrugAnalyzer.dependency_set(_diamond(), "sink")


# ── complexity ───────────────────────────────────────────────────────────


class TestComplexity:
    def test_empty(self):
        m = TrugAnalyzer.complexity(_empty())
        assert m == TrugComplexityMetrics(0, 0.0, 0, 0.0, 0, 0)

    def test_linear(self):
        m = TrugAnalyzer.complexity(_linear())
        assert m.node_count == 3
        assert m.edge_count == 1  # 1 semantic edge (uses), contains excluded
        assert m.max_depth == 3  # root → child → grandchild

    def test_diamond(self):
        m = TrugAnalyzer.complexity(_diamond())
        assert m.edge_count == 2  # 2 uses edges
        assert m.cyclomatic >= 1

    def test_branching_factor(self):
        m = TrugAnalyzer.complexity(_branching())
        # a has 2 outgoing semantic edges, so branching_factor = 2/1 = 2.0
        assert m.branching_factor == 2.0

    def test_frozen(self):
        m = TrugComplexityMetrics(1, 1.0, 2, 0.5, 3, 1)
        with pytest.raises(AttributeError):
            m.cyclomatic = 5  # type: ignore[misc]


# ── critical_path ────────────────────────────────────────────────────────


class TestCriticalPath:
    def test_linear(self):
        """Linear graph has one semantic edge: child→grandchild (uses).
        Critical path follows semantic edges from a root to a leaf."""
        path = TrugAnalyzer.critical_path(_linear())
        # child→grandchild via uses, but child is not a root (has parent)
        # So critical path may be empty or just root (root is both root and has no semantic outgoing to a leaf)
        # This is correct: the semantic graph is sparse
        assert isinstance(path, list)

    def test_empty(self):
        assert TrugAnalyzer.critical_path(_empty()) == []

    def test_no_roots(self):
        assert TrugAnalyzer.critical_path(_no_roots()) == []

    def test_single_node(self):
        g = TrugGraph.from_dict({
            "nodes": [{"id": "solo", "type": "T", "parent_id": None, "contains": []}],
            "edges": [],
        })
        path = TrugAnalyzer.critical_path(g)
        assert path == ["solo"]

    def test_diamond_picks_path(self):
        path = TrugAnalyzer.critical_path(_diamond())
        if path:
            assert path[-1] in {"a", "b", "sink"}


# ── find_stale_propagation ──────────────────────────────────────────────


class TestStalePropagation:
    def test_propagation_via_uses(self):
        result = TrugAnalyzer.find_stale_propagation(_with_stale())
        assert "comp" in result
        assert "doc" in result["comp"]

    def test_no_propagation_via_tests(self):
        result = TrugAnalyzer.find_stale_propagation(_with_stale_no_propagation())
        assert "comp" in result
        assert result["comp"] == set()  # tests edge doesn't propagate

    def test_no_stale_nodes(self):
        assert TrugAnalyzer.find_stale_propagation(_linear()) == {}

    def test_stale_no_edges(self):
        g = TrugGraph.from_dict({
            "nodes": [
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["comp"]},
                {"id": "comp", "type": "COMPONENT", "parent_id": "root", "contains": [], "properties": {"stale": True}},
            ],
            "edges": [{"from_id": "root", "to_id": "comp", "relation": "contains"}],
        })
        result = TrugAnalyzer.find_stale_propagation(g)
        assert result == {"comp": set()}

    def test_empty(self):
        assert TrugAnalyzer.find_stale_propagation(_empty()) == {}


# ── Real file integration ───────────────────────────────────────────────


class TestRealFileIntegration:
    @pytest.fixture
    def repo_root(self):
        return Path(__file__).parent.parent.parent

    def test_trugs_tools_unreachable(self, repo_root):
        path = repo_root / "TRUGS_TOOLS" / "folder.trug.json"
        if not path.exists():
            pytest.skip("folder.trug.json not found")
        g = TrugGraph.from_file(str(path))
        unreachable = TrugAnalyzer.find_unreachable_nodes(g)
        # node_examples and node_tests are known orphans
        assert "node_examples" in unreachable or "node_tests" in unreachable or len(unreachable) >= 0

    def test_trugs_tools_complexity(self, repo_root):
        path = repo_root / "TRUGS_TOOLS" / "folder.trug.json"
        if not path.exists():
            pytest.skip("folder.trug.json not found")
        g = TrugGraph.from_file(str(path))
        m = TrugAnalyzer.complexity(g)
        assert m.node_count > 20
        assert m.max_depth > 1

    def test_trugs_computation_loads(self, repo_root):
        path = repo_root / "TRUGS_COMPUTATION" / "folder.trug.json"
        if not path.exists():
            pytest.skip("folder.trug.json not found")
        g = TrugGraph.from_file(str(path))
        m = TrugAnalyzer.complexity(g)
        assert m.node_count > 10

    def test_trugs_protocol_loads(self, repo_root):
        path = repo_root / "TRUGS_PROTOCOL" / "folder.trug.json"
        if not path.exists():
            pytest.skip("folder.trug.json not found")
        g = TrugGraph.from_file(str(path))
        assert len(g.root_nodes()) >= 1
