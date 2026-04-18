"""Tests for TrugGraph — domain-agnostic graph model (#618)."""

import json
import pytest
from pathlib import Path

from trugs_tools.trug_graph import TrugGraph


# ── Helpers ──────────────────────────────────────────────────────────────


def _minimal():
    """Single root with two children."""
    return TrugGraph.from_dict({
        "name": "test",
        "version": "1.0.0",
        "type": "PROJECT",
        "capabilities": {"extensions": [], "vocabularies": ["project_v1"]},
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child1", "child2"], "metric_level": "KILO_FOLDER"},
            {"id": "child1", "type": "COMPONENT", "parent_id": "root", "contains": [], "metric_level": "BASE_COMPONENT"},
            {"id": "child2", "type": "DOCUMENT", "parent_id": "root", "contains": [], "metric_level": "BASE_DOCUMENT"},
        ],
        "edges": [
            {"from_id": "root", "to_id": "child1", "relation": "contains"},
            {"from_id": "root", "to_id": "child2", "relation": "contains"},
            {"from_id": "child1", "to_id": "child2", "relation": "uses"},
        ],
    })


def _with_hierarchy():
    """Root → mid → leaf, plus semantic edge."""
    return TrugGraph.from_dict({
        "capabilities": {"extensions": [], "vocabularies": []},
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["mid"]},
            {"id": "mid", "type": "COMPONENT", "parent_id": "root", "contains": ["leaf"]},
            {"id": "leaf", "type": "DOCUMENT", "parent_id": "mid", "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "mid", "relation": "contains"},
            {"from_id": "mid", "to_id": "leaf", "relation": "contains"},
            {"from_id": "leaf", "to_id": "root", "relation": "describes"},
        ],
    })


def _with_orphan():
    """Minimal graph + one orphan node (no parent, no edges)."""
    return TrugGraph.from_dict({
        "capabilities": {"extensions": [], "vocabularies": []},
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child"]},
            {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": []},
            {"id": "orphan", "type": "COMPONENT", "parent_id": None, "contains": []},
        ],
        "edges": [
            {"from_id": "root", "to_id": "child", "relation": "contains"},
        ],
    })


def _with_stale():
    """Graph with one stale node."""
    return TrugGraph.from_dict({
        "capabilities": {"extensions": [], "vocabularies": []},
        "nodes": [
            {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["comp"]},
            {"id": "comp", "type": "COMPONENT", "parent_id": "root", "contains": [], "properties": {"stale": True, "stale_reason": "file not found"}},
        ],
        "edges": [
            {"from_id": "root", "to_id": "comp", "relation": "contains"},
        ],
    })


def _empty():
    return TrugGraph.from_dict({"nodes": [], "edges": []})


def _with_from_node():
    """Edges using from_node/to_node instead of from_id/to_id."""
    return TrugGraph.from_dict({
        "capabilities": {"extensions": [], "vocabularies": []},
        "nodes": [
            {"id": "a", "type": "FOLDER", "parent_id": None, "contains": ["b"]},
            {"id": "b", "type": "COMPONENT", "parent_id": "a", "contains": []},
        ],
        "edges": [
            {"from_node": "a", "to_node": "b", "relation": "contains"},
        ],
    })


# ── Factory tests ────────────────────────────────────────────────────────


class TestFactories:
    def test_from_dict(self):
        g = _minimal()
        assert g.get_node("root") is not None

    def test_from_json(self):
        trug = {"nodes": [{"id": "x", "type": "T", "parent_id": None, "contains": []}], "edges": []}
        g = TrugGraph.from_json(json.dumps(trug))
        assert g.node_ids() == {"x"}

    def test_from_file(self, tmp_path):
        p = tmp_path / "t.json"
        p.write_text(json.dumps({"nodes": [{"id": "x", "type": "T", "parent_id": None, "contains": []}], "edges": []}))
        g = TrugGraph.from_file(str(p))
        assert g.node_ids() == {"x"}

    def test_from_node_normalized(self):
        g = _with_from_node()
        edges = g.get_all_edges()
        assert len(edges) == 1
        assert edges[0].get("from_id") == "a"

    def test_metadata_preserved(self):
        g = _minimal()
        assert g.store.get_metadata().get("name") == "test"


# ── Node accessors ───────────────────────────────────────────────────────


class TestNodeAccessors:
    def test_get_node(self):
        g = _minimal()
        assert g.get_node("root") is not None
        assert g.get_node("nonexistent") is None

    def test_get_all_nodes(self):
        assert len(_minimal().get_all_nodes()) == 3

    def test_get_nodes_by_type(self):
        g = _minimal()
        assert len(g.get_nodes_by_type("FOLDER")) == 1
        assert len(g.get_nodes_by_type("MISSING")) == 0

    def test_node_ids(self):
        assert _minimal().node_ids() == {"root", "child1", "child2"}

    def test_empty(self):
        g = _empty()
        assert g.get_all_nodes() == []
        assert g.node_ids() == set()


# ── Hierarchy accessors ──────────────────────────────────────────────────


class TestHierarchy:
    def test_root_nodes(self):
        assert _minimal().root_nodes() == ["root"]

    def test_root_nodes_multiple(self):
        g = _with_orphan()
        roots = g.root_nodes()
        assert "root" in roots
        assert "orphan" in roots

    def test_leaf_nodes(self):
        leaves = _minimal().leaf_nodes()
        assert "child1" in leaves
        assert "child2" in leaves
        assert "root" not in leaves

    def test_get_children(self):
        assert _minimal().get_children("root") == ["child1", "child2"]
        assert _minimal().get_children("child1") == []
        assert _minimal().get_children("nonexistent") == []

    def test_get_parent(self):
        g = _minimal()
        assert g.get_parent("child1") == "root"
        assert g.get_parent("root") is None
        assert g.get_parent("nonexistent") is None

    def test_get_ancestors(self):
        g = _with_hierarchy()
        assert g.get_ancestors("leaf") == ["mid", "root"]
        assert g.get_ancestors("root") == []

    def test_get_ancestors_no_infinite_loop(self):
        """Malformed data with circular parent_id should not loop."""
        g = TrugGraph.from_dict({
            "nodes": [
                {"id": "a", "type": "T", "parent_id": "b", "contains": []},
                {"id": "b", "type": "T", "parent_id": "a", "contains": []},
            ],
            "edges": [],
        })
        ancestors = g.get_ancestors("a")
        assert len(ancestors) == 1  # stops at cycle
        assert "b" in ancestors

    def test_get_descendants(self):
        g = _with_hierarchy()
        assert g.get_descendants("root") == {"mid", "leaf"}
        assert g.get_descendants("leaf") == set()

    def test_empty_hierarchy(self):
        g = _empty()
        assert g.root_nodes() == []
        assert g.leaf_nodes() == []


# ── Edge accessors ───────────────────────────────────────────────────────


class TestEdgeAccessors:
    def test_get_all_edges(self):
        assert len(_minimal().get_all_edges()) == 3

    def test_get_edges_by_relation(self):
        g = _minimal()
        assert len(g.get_edges_by_relation("contains")) == 2
        assert len(g.get_edges_by_relation("uses")) == 1
        assert len(g.get_edges_by_relation("missing")) == 0

    def test_get_outgoing(self):
        g = _minimal()
        out = g.get_outgoing("root")
        assert len(out) == 2  # two contains edges

    def test_get_incoming(self):
        g = _minimal()
        inc = g.get_incoming("child2")
        assert len(inc) == 2  # one contains + one uses

    def test_get_semantic_edges(self):
        g = _minimal()
        semantic = g.get_semantic_edges()
        assert len(semantic) == 1
        assert semantic[0]["relation"] == "uses"

    def test_empty_edges(self):
        assert _empty().get_all_edges() == []
        assert _empty().get_semantic_edges() == []


# ── Stale accessors ──────────────────────────────────────────────────────


class TestStaleAccessors:
    def test_get_stale_nodes(self):
        g = _with_stale()
        assert g.get_stale_nodes() == ["comp"]

    def test_is_stale(self):
        g = _with_stale()
        assert g.is_stale("comp") is True
        assert g.is_stale("root") is False
        assert g.is_stale("nonexistent") is False

    def test_no_stale(self):
        assert _minimal().get_stale_nodes() == []


# ── Metadata ─────────────────────────────────────────────────────────────


class TestMetadata:
    def test_vocabularies(self):
        assert _minimal().vocabularies() == ["project_v1"]

    def test_extensions(self):
        assert _minimal().extensions() == []

    def test_store_property(self):
        assert _minimal().store is not None

    def test_edge_from(self):
        assert TrugGraph.edge_from({"from_id": "a"}) == "a"
        assert TrugGraph.edge_from({"from_node": "b"}) == "b"

    def test_edge_to(self):
        assert TrugGraph.edge_to({"to_id": "a"}) == "a"
        assert TrugGraph.edge_to({"to_node": "b"}) == "b"


# ── Real file integration ───────────────────────────────────────────────


class TestRealFiles:
    @pytest.fixture
    def repo_root(self):
        return Path(__file__).parent.parent.parent  # TRUGS-DEVELOPMENT/

    def test_load_trugs_tools_folder(self, repo_root):
        path = repo_root / "TRUGS_TOOLS" / "folder.trug.json"
        if not path.exists():
            pytest.skip("folder.trug.json not found")
        g = TrugGraph.from_file(str(path))
        assert len(g.get_all_nodes()) > 20
        roots = g.root_nodes()
        assert "trugs_tools_folder" in roots

    def test_load_trugs_computation_folder(self, repo_root):
        path = repo_root / "TRUGS_COMPUTATION" / "folder.trug.json"
        if not path.exists():
            pytest.skip("folder.trug.json not found")
        g = TrugGraph.from_file(str(path))
        assert len(g.get_all_nodes()) > 10
