"""Tests for trugs_tools.web.hub.cross_trug_edges."""

import pytest

from trugs_tools.web.hub.cross_trug_edges import (
    CrossTrugUri,
    CrossTrugEdge,
    parse_cross_trug_uri,
    is_cross_trug_ref,
    build_cross_trug_uri,
    validate_cross_trug_edge,
    CrossTrugResolver,
)


# ============================================================================
# URI parsing
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testparsecrosstruguri AS A RECORD test_suite.
class TestParseCrossTrugUri:
    # AGENT SHALL VALIDATE PROCESS test_full_uri.
    def test_full_uri(self):
        uri = parse_cross_trug_uri(
            "trug://github.com/user/repo/folder.trug.json#node-42"
        )
        assert uri is not None
        assert uri.authority == "github.com"
        assert uri.path == "/user/repo/folder.trug.json"
        assert uri.node_id == "node-42"
        assert uri.is_valid is True

    # AGENT SHALL VALIDATE PROCESS test_minimal_uri.
    def test_minimal_uri(self):
        uri = parse_cross_trug_uri("trug://example.com/data.trug.json#root")
        assert uri is not None
        assert uri.authority == "example.com"
        assert uri.node_id == "root"

    # AGENT SHALL VALIDATE PROCESS test_missing_fragment.
    def test_missing_fragment(self):
        uri = parse_cross_trug_uri("trug://example.com/data.trug.json")
        assert uri is not None
        assert uri.node_id == ""
        assert uri.is_valid is False

    # AGENT SHALL VALIDATE PROCESS test_missing_authority.
    def test_missing_authority(self):
        uri = parse_cross_trug_uri("trug:///path/only#node")
        assert uri is not None
        assert uri.authority == ""
        assert uri.is_valid is False

    # AGENT SHALL VALIDATE PROCESS test_non_trug_scheme.
    def test_non_trug_scheme(self):
        uri = parse_cross_trug_uri("https://example.com/foo#bar")
        assert uri is None

    # AGENT SHALL VALIDATE PROCESS test_not_a_string.
    def test_not_a_string(self):
        assert parse_cross_trug_uri(42) is None
        assert parse_cross_trug_uri(None) is None

    # AGENT SHALL VALIDATE PROCESS test_empty_string.
    def test_empty_string(self):
        assert parse_cross_trug_uri("") is None

    # AGENT SHALL VALIDATE PROCESS test_whitespace_stripped.
    def test_whitespace_stripped(self):
        uri = parse_cross_trug_uri("  trug://example.com/a.trug.json#x  ")
        assert uri is not None
        assert uri.node_id == "x"


# AGENT claude SHALL DEFINE RECORD testcrosstruguri AS A RECORD test_suite.
class TestCrossTrugUri:
    # AGENT SHALL VALIDATE PROCESS test_trug_location.
    def test_trug_location(self):
        uri = CrossTrugUri(authority="example.com", path="/a.trug.json", node_id="n1")
        assert uri.trug_location == "trug://example.com/a.trug.json"

    # AGENT SHALL VALIDATE PROCESS test_to_uri.
    def test_to_uri(self):
        uri = CrossTrugUri(authority="example.com", path="/a.trug.json", node_id="n1")
        assert uri.to_uri() == "trug://example.com/a.trug.json#n1"

    # AGENT SHALL VALIDATE PROCESS test_is_valid_all_fields.
    def test_is_valid_all_fields(self):
        uri = CrossTrugUri(authority="h", path="/p", node_id="n")
        assert uri.is_valid is True

    # AGENT SHALL VALIDATE PROCESS test_is_valid_missing_node_id.
    def test_is_valid_missing_node_id(self):
        uri = CrossTrugUri(authority="h", path="/p", node_id="")
        assert uri.is_valid is False


# AGENT claude SHALL DEFINE RECORD testiscrosstrugref AS A RECORD test_suite.
class TestIsCrossTrugRef:
    # AGENT SHALL VALIDATE PROCESS test_positive.
    def test_positive(self):
        assert is_cross_trug_ref("trug://example.com/a#b") is True

    # AGENT SHALL VALIDATE PROCESS test_negative_plain_id.
    def test_negative_plain_id(self):
        assert is_cross_trug_ref("my-node-id") is False

    # AGENT SHALL VALIDATE PROCESS test_negative_http.
    def test_negative_http(self):
        assert is_cross_trug_ref("https://example.com") is False

    # AGENT SHALL VALIDATE PROCESS test_non_string.
    def test_non_string(self):
        assert is_cross_trug_ref(42) is False


# AGENT claude SHALL DEFINE RECORD testbuildcrosstruguri AS A RECORD test_suite.
class TestBuildCrossTrugUri:
    # AGENT SHALL VALIDATE PROCESS test_basic.
    def test_basic(self):
        uri = build_cross_trug_uri("example.com", "/a.trug.json", "node-1")
        assert uri == "trug://example.com/a.trug.json#node-1"

    # AGENT SHALL VALIDATE PROCESS test_path_without_leading_slash.
    def test_path_without_leading_slash(self):
        uri = build_cross_trug_uri("example.com", "a.trug.json", "node-1")
        assert uri == "trug://example.com/a.trug.json#node-1"


# ============================================================================
# CrossTrugEdge
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testcrosstrugedge AS A RECORD test_suite.
class TestCrossTrugEdge:
    # AGENT SHALL VALIDATE PROCESS test_is_cross_trug_to_id.
    def test_is_cross_trug_to_id(self):
        edge = CrossTrugEdge(
            from_id="local-node",
            to_id="trug://example.com/a.trug.json#remote-node",
            relation="REFERENCES",
        )
        assert edge.is_cross_trug is True

    # AGENT SHALL VALIDATE PROCESS test_is_cross_trug_from_id.
    def test_is_cross_trug_from_id(self):
        edge = CrossTrugEdge(
            from_id="trug://example.com/a.trug.json#src-node",
            to_id="local-node",
            relation="REFERENCES",
        )
        assert edge.is_cross_trug is True

    # AGENT SHALL VALIDATE PROCESS test_not_cross_trug.
    def test_not_cross_trug(self):
        edge = CrossTrugEdge(
            from_id="local-a",
            to_id="local-b",
            relation="CITES",
        )
        assert edge.is_cross_trug is False

    # AGENT SHALL VALIDATE PROCESS test_remote_uri_prefers_to_id.
    def test_remote_uri_prefers_to_id(self):
        edge = CrossTrugEdge(
            from_id="trug://a.com/x#f",
            to_id="trug://b.com/y#t",
            relation="LINKS",
        )
        uri = edge.remote_uri
        assert uri is not None
        assert uri.authority == "b.com"

    # AGENT SHALL VALIDATE PROCESS test_remote_uri_from_id_fallback.
    def test_remote_uri_from_id_fallback(self):
        edge = CrossTrugEdge(
            from_id="trug://a.com/x#f",
            to_id="local",
            relation="LINKS",
        )
        uri = edge.remote_uri
        assert uri is not None
        assert uri.authority == "a.com"

    # AGENT SHALL VALIDATE PROCESS test_remote_uri_none_for_local.
    def test_remote_uri_none_for_local(self):
        edge = CrossTrugEdge(from_id="a", to_id="b", relation="X")
        assert edge.remote_uri is None

    # AGENT SHALL VALIDATE PROCESS test_to_edge_dict.
    def test_to_edge_dict(self):
        edge = CrossTrugEdge(
            from_id="local",
            to_id="trug://example.com/a#remote",
            relation="CITES",
            weight=0.8,
        )
        d = edge.to_edge_dict()
        assert d["from_id"] == "local"
        assert d["to_id"] == "trug://example.com/a#remote"
        assert d["relation"] == "CITES"
        assert d["weight"] == 0.8

    # AGENT SHALL VALIDATE PROCESS test_default_weight.
    def test_default_weight(self):
        edge = CrossTrugEdge(from_id="a", to_id="b", relation="X")
        assert edge.weight == 0.5


# ============================================================================
# Validation
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testvalidatecrosstrugedge AS A RECORD test_suite.
class TestValidateCrossTrugEdge:
    # AGENT SHALL VALIDATE PROCESS test_valid_edge.
    def test_valid_edge(self):
        edge = CrossTrugEdge(
            from_id="local",
            to_id="trug://example.com/a.trug.json#node-1",
            relation="CITES",
            weight=0.8,
        )
        errors = validate_cross_trug_edge(edge)
        assert errors == []

    # AGENT SHALL VALIDATE PROCESS test_no_cross_trug_ref.
    def test_no_cross_trug_ref(self):
        edge = CrossTrugEdge(
            from_id="local-a",
            to_id="local-b",
            relation="CITES",
        )
        errors = validate_cross_trug_edge(edge)
        assert any("Neither" in e for e in errors)

    # AGENT SHALL VALIDATE PROCESS test_invalid_uri.
    def test_invalid_uri(self):
        edge = CrossTrugEdge(
            from_id="local",
            to_id="trug:///no-authority#node",
            relation="CITES",
        )
        errors = validate_cross_trug_edge(edge)
        assert any("not a valid" in e for e in errors)

    # AGENT SHALL VALIDATE PROCESS test_missing_relation.
    def test_missing_relation(self):
        edge = CrossTrugEdge(
            from_id="local",
            to_id="trug://example.com/a#n",
            relation="",
        )
        errors = validate_cross_trug_edge(edge)
        assert any("relation" in e for e in errors)

    # AGENT SHALL VALIDATE PROCESS test_weight_out_of_range.
    def test_weight_out_of_range(self):
        edge = CrossTrugEdge(
            from_id="local",
            to_id="trug://example.com/a#n",
            relation="CITES",
            weight=1.5,
        )
        errors = validate_cross_trug_edge(edge)
        assert any("weight" in e for e in errors)

    # AGENT SHALL VALIDATE PROCESS test_weight_negative.
    def test_weight_negative(self):
        edge = CrossTrugEdge(
            from_id="local",
            to_id="trug://example.com/a#n",
            relation="CITES",
            weight=-0.1,
        )
        errors = validate_cross_trug_edge(edge)
        assert any("weight" in e for e in errors)

    # AGENT SHALL VALIDATE PROCESS test_multiple_errors.
    def test_multiple_errors(self):
        edge = CrossTrugEdge(
            from_id="local-a",
            to_id="local-b",
            relation="",
            weight=2.0,
        )
        errors = validate_cross_trug_edge(edge)
        assert len(errors) >= 2


# ============================================================================
# CrossTrugResolver
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testcrosstrugresolver AS A RECORD test_suite.
class TestCrossTrugResolver:
    def _sample_graph(self, node_id="node-1"):
        return {
            "nodes": [
                {
                    "id": node_id,
                    "type": "CONCEPT",
                    "properties": {"name": "Test Node"},
                }
            ],
            "edges": [],
        }

    # AGENT SHALL VALIDATE PROCESS test_register_and_resolve.
    def test_register_and_resolve(self):
        resolver = CrossTrugResolver()
        resolver.register_graph(
            "trug://example.com/a.trug.json",
            self._sample_graph("node-1"),
        )
        node = resolver.resolve_node("trug://example.com/a.trug.json#node-1")
        assert node is not None
        assert node["id"] == "node-1"

    # AGENT SHALL VALIDATE PROCESS test_resolve_missing_node.
    def test_resolve_missing_node(self):
        resolver = CrossTrugResolver()
        resolver.register_graph(
            "trug://example.com/a.trug.json",
            self._sample_graph("node-1"),
        )
        node = resolver.resolve_node("trug://example.com/a.trug.json#node-999")
        assert node is None

    # AGENT SHALL VALIDATE PROCESS test_resolve_missing_graph.
    def test_resolve_missing_graph(self):
        resolver = CrossTrugResolver()
        node = resolver.resolve_node("trug://unknown.com/a.trug.json#node-1")
        assert node is None

    # AGENT SHALL VALIDATE PROCESS test_resolve_invalid_uri.
    def test_resolve_invalid_uri(self):
        resolver = CrossTrugResolver()
        assert resolver.resolve_node("not-a-uri") is None

    # AGENT SHALL VALIDATE PROCESS test_resolve_edge_to_id.
    def test_resolve_edge_to_id(self):
        resolver = CrossTrugResolver()
        resolver.register_graph(
            "trug://example.com/a.trug.json",
            self._sample_graph("remote-node"),
        )
        edge = CrossTrugEdge(
            from_id="local-node",
            to_id="trug://example.com/a.trug.json#remote-node",
            relation="CITES",
        )
        result = resolver.resolve_edge(edge)
        assert result["to_node"] is not None
        assert result["from_node"] is None  # local ref, not resolved
        assert result["resolved"] is True

    # AGENT SHALL VALIDATE PROCESS test_resolve_edge_from_id.
    def test_resolve_edge_from_id(self):
        resolver = CrossTrugResolver()
        resolver.register_graph(
            "trug://example.com/a.trug.json",
            self._sample_graph("src-node"),
        )
        edge = CrossTrugEdge(
            from_id="trug://example.com/a.trug.json#src-node",
            to_id="local-node",
            relation="CITES",
        )
        result = resolver.resolve_edge(edge)
        assert result["from_node"] is not None
        assert result["resolved"] is True

    # AGENT SHALL VALIDATE PROCESS test_resolve_edge_neither_remote.
    def test_resolve_edge_neither_remote(self):
        resolver = CrossTrugResolver()
        edge = CrossTrugEdge(from_id="a", to_id="b", relation="X")
        result = resolver.resolve_edge(edge)
        assert result["from_node"] is None
        assert result["to_node"] is None
        assert result["resolved"] is False

    # AGENT SHALL VALIDATE PROCESS test_register_loader.
    def test_register_loader(self):
        resolver = CrossTrugResolver()
        graph_store = {
            "trug://dynamic.com/a.trug.json": self._sample_graph("dyn-node"),
        }
        resolver.register_loader(lambda loc: graph_store.get(loc))
        node = resolver.resolve_node("trug://dynamic.com/a.trug.json#dyn-node")
        assert node is not None
        assert node["id"] == "dyn-node"

    # AGENT SHALL VALIDATE PROCESS test_loader_caches.
    def test_loader_caches(self):
        call_count = [0]

        # AGENT claude SHALL DEFINE FUNCTION counting_loader.
        def counting_loader(loc):
            call_count[0] += 1
            return {"nodes": [{"id": "n1", "type": "T", "properties": {}}]}

        resolver = CrossTrugResolver()
        resolver.register_loader(counting_loader)
        resolver.resolve_node("trug://x.com/a#n1")
        resolver.resolve_node("trug://x.com/a#n1")
        assert call_count[0] == 1  # Loaded once, then cached

    # AGENT SHALL VALIDATE PROCESS test_loader_returns_none.
    def test_loader_returns_none(self):
        resolver = CrossTrugResolver()
        resolver.register_loader(lambda loc: None)
        node = resolver.resolve_node("trug://unknown.com/a#n1")
        assert node is None

    # AGENT SHALL VALIDATE PROCESS test_loader_raises_exception.
    def test_loader_raises_exception(self):
        # AGENT claude SHALL DEFINE FUNCTION bad_loader.
        def bad_loader(loc):
            raise RuntimeError("oops")

        resolver = CrossTrugResolver()
        resolver.register_loader(bad_loader)
        node = resolver.resolve_node("trug://bad.com/a#n1")
        assert node is None  # Graceful failure

    # AGENT SHALL VALIDATE PROCESS test_cached_locations.
    def test_cached_locations(self):
        resolver = CrossTrugResolver()
        resolver.register_graph("trug://a.com/x", {"nodes": []})
        resolver.register_graph("trug://b.com/y", {"nodes": []})
        assert len(resolver.cached_locations) == 2
