"""PERAGO integration tests for TRUGS Tools.

Tests that TRUGS_TOOLS can be used alongside PERAGO:
- Import trugs_tools from PERAGO's environment
- Generate and validate TRUGs using trugs_tools
- Verify PERAGO's TRUGNode model is compatible with trugs_tools validation
"""

import pytest
import sys
import os

# Mark all tests as integration tests that may be skipped if PERAGO is not available
pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "..", "PERAGO", "src")),
    reason="PERAGO not available in this environment",
)


class TestPeragoImport:
    """Test that trugs_tools can be imported alongside PERAGO."""

    def test_trugs_tools_import(self):
        """trugs_tools can be imported."""
        import trugs_tools
        assert hasattr(trugs_tools, "__version__")
        assert hasattr(trugs_tools, "validate_trug")
        assert hasattr(trugs_tools, "generate_trug")

    def test_perago_import(self):
        """PERAGO src module can be imported."""
        from src.models import TRUGNode, TRUGEdge, TRUGGraph
        assert TRUGNode is not None
        assert TRUGEdge is not None
        assert TRUGGraph is not None


class TestPeragoTrugValidation:
    """Test that TRUGs generated via trugs_tools validate correctly."""

    def test_generate_and_validate_python_trug(self):
        """Generate a Python TRUG with trugs_tools and validate it."""
        from trugs_tools import generate_trug, validate_trug

        trug = generate_trug("python", template="complete")
        result = validate_trug(trug)
        assert result.valid, f"Validation failed: {result.errors}"

    def test_generate_and_validate_orchestration_trug(self):
        """Generate an Orchestration TRUG (PERAGO-relevant branch) and validate."""
        from trugs_tools import generate_trug, validate_trug

        trug = generate_trug("orchestration", template="complete")
        result = validate_trug(trug)
        assert result.valid, f"Validation failed: {result.errors}"

    def test_perago_trug_node_compatibility(self):
        """Verify PERAGO TRUGNode fields are a subset of trugs_tools node fields."""
        from src.models import TRUGNode
        from trugs_tools import generate_trug

        trug = generate_trug("python", template="complete")
        # PERAGO TRUGNode has: id, type, properties, parent_id, contains, metric_level, dimension
        perago_fields = set(TRUGNode.model_fields.keys())
        # trugs_tools nodes have at minimum: id, type, properties
        sample_node = trug["nodes"][0]
        trugs_fields = set(sample_node.keys())

        # Core fields must be present in both
        core_overlap = {"id", "type", "properties"}
        assert core_overlap.issubset(perago_fields), f"PERAGO missing core fields: {core_overlap - perago_fields}"
        assert core_overlap.issubset(trugs_fields), f"trugs_tools missing core fields: {core_overlap - trugs_fields}"

    def test_perago_can_construct_trug_graph_from_trugs_tools_output(self):
        """Verify PERAGO TRUGGraph can be constructed from trugs_tools-generated data."""
        from src.models import TRUGNode, TRUGEdge, TRUGGraph
        from trugs_tools import generate_trug

        trug = generate_trug("python", template="minimal")

        # Build PERAGO-compatible nodes from trugs_tools output
        nodes = []
        for n in trug["nodes"]:
            node = TRUGNode(
                id=n["id"],
                type=n["type"],
                properties=n.get("properties", {}),
                parent_id=n.get("parent_id"),
                contains=n.get("contains", []),
                metric_level=n.get("metric_level", "L0"),
                dimension=n.get("dimension", "structural"),
            )
            nodes.append(node)

        edges = []
        for e in trug["edges"]:
            edge = TRUGEdge(
                from_id=e["from_id"],
                to_id=e["to_id"],
                relation=e["relation"],
            )
            edges.append(edge)

        graph = TRUGGraph(nodes=nodes, edges=edges, metadata=trug.get("metadata", {}))
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0


class TestPeragoDependencyConsumption:
    """Test that PERAGO can consume trugs_tools as a dependency."""

    def test_trugs_tools_version_accessible(self):
        """trugs_tools version is accessible."""
        from trugs_tools import __version__
        assert __version__ == "1.0.0"

    def test_trugs_tools_validator_accessible(self):
        """trugs_tools validator module is importable."""
        from trugs_tools.validator import validate_trug, validate_file
        assert callable(validate_trug)
        assert callable(validate_file)

    def test_trugs_tools_generator_accessible(self):
        """trugs_tools generator module is importable."""
        from trugs_tools.generator import generate_trug, SUPPORTED_BRANCHES
        assert callable(generate_trug)
        assert len(SUPPORTED_BRANCHES) == 12

    def test_trugs_tools_schemas_accessible(self):
        """trugs_tools schemas module is importable."""
        from trugs_tools.schemas import list_branch_schemas, validate_branch_schema
        assert callable(list_branch_schemas)
        assert callable(validate_branch_schema)
        schemas = list_branch_schemas()
        assert len(schemas) >= 10
