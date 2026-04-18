"""TRUGS_RESEARCH integration tests for TRUGS Tools.

Tests that TRUGS_TOOLS can validate research-branch TRUGs:
- Locates TRUGS_RESEARCH/HUBS/*.json files if they exist
- Validates research graphs with trugs-validate
- Generates README.md from research graphs with trugs-render
- Verifies validation and rendering produce valid output
"""

import pytest
import json
import glob
import os

from trugs_tools import validate_trug, generate_trug
from trugs_tools.renderer import render_all

TRUGS_RESEARCH_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "TRUGS_RESEARCH"
)
HUBS_DIR = os.path.join(TRUGS_RESEARCH_DIR, "HUBS")

pytestmark = pytest.mark.skipif(
    not os.path.exists(TRUGS_RESEARCH_DIR),
    reason="TRUGS_RESEARCH not available in this environment",
)


# AGENT claude SHALL DEFINE FUNCTION get_hub_json_files.
def get_hub_json_files():
    """Discover all JSON files in TRUGS_RESEARCH/HUBS/."""
    if not os.path.exists(HUBS_DIR):
        return []
    return sorted(glob.glob(os.path.join(HUBS_DIR, "*.json")))


# AGENT claude SHALL DEFINE RECORD testtrugsresearchavailability AS A RECORD test_suite.
class TestTrugsResearchAvailability:
    """Test that TRUGS_RESEARCH directory is accessible."""

    # AGENT SHALL VALIDATE PROCESS test_trugs_research_exists.
    def test_trugs_research_exists(self):
        """TRUGS_RESEARCH directory exists."""
        assert os.path.isdir(TRUGS_RESEARCH_DIR)

    # AGENT SHALL VALIDATE PROCESS test_trugs_research_has_specification.
    def test_trugs_research_has_specification(self):
        """TRUGS_RESEARCH has a RESEARCH_BRANCH specification."""
        spec_path = os.path.join(TRUGS_RESEARCH_DIR, "RESEARCH_BRANCH", "SPEC_research_branch.md")
        assert os.path.exists(spec_path), "RESEARCH_BRANCH/SPEC_research_branch.md not found"


# AGENT claude SHALL DEFINE RECORD testresearchgraphvalidation AS A RECORD test_suite.
class TestResearchGraphValidation:
    """Test validation of research-style TRUGs."""

    # AGENT claude SHALL DEFINE FUNCTION research_trug.
    @pytest.fixture
    def research_trug(self):
        """Create a sample research-style TRUG for validation."""
        return {
            "name": "research_graph_test",
            "version": "1.0.0",
            "type": "KNOWLEDGE",
            "branch": "knowledge",
            "nodes": [
                {
                    "id": "class_graph_theory",
                    "type": "CLASS",
                    "metric_level": "KILO_CLASS",
                    "parent_id": None,
                    "properties": {
                        "name": "Graph Theory",
                        "definition": "Study of graphs",
                        "domain": "mathematics",
                    },
                },
                {
                    "id": "entity_node",
                    "type": "ENTITY",
                    "metric_level": "BASE_ENTITY",
                    "parent_id": "class_graph_theory",
                    "properties": {
                        "name": "Node",
                        "definition": "A fundamental unit in a graph",
                        "domain": "mathematics",
                    },
                },
                {
                    "id": "entity_edge",
                    "type": "ENTITY",
                    "metric_level": "BASE_ENTITY",
                    "parent_id": "class_graph_theory",
                    "properties": {
                        "name": "Edge",
                        "definition": "A connection between nodes",
                        "domain": "mathematics",
                    },
                },
            ],
            "edges": [
                {"from_id": "class_graph_theory", "to_id": "entity_node", "relation": "contains"},
                {"from_id": "class_graph_theory", "to_id": "entity_edge", "relation": "contains"},
                {"from_id": "entity_node", "to_id": "entity_edge", "relation": "related_to"},
            ],
            "metadata": {
                "created": "2026-02-17",
                "source": "TRUGS_RESEARCH",
            },
        }

    # AGENT SHALL VALIDATE PROCESS test_research_trug_validates.
    def test_research_trug_validates(self, research_trug):
        """A research-style TRUG passes validation."""
        result = validate_trug(research_trug)
        assert result.valid, f"Validation failed: {result.errors}"

    # AGENT SHALL VALIDATE PROCESS test_research_trug_renders.
    def test_research_trug_renders(self, research_trug, tmp_path):
        """A research-style TRUG can be rendered to markdown."""
        output = render_all(research_trug, output_dir=str(tmp_path), render_date="2026-02-17")
        assert isinstance(output, dict)
        # Rendered output should contain markdown content
        for key, value in output.items():
            if isinstance(value, str):
                assert len(value) > 0

    # AGENT SHALL VALIDATE PROCESS test_validate_hub_files.
    def test_validate_hub_files(self):
        """Validate any existing HUBS/*.json files."""
        hub_files = get_hub_json_files()
        if not hub_files:
            pytest.skip("No HUBS/*.json files found (TRUGS_RESEARCH HUBS not yet populated)")

        for filepath in hub_files:
            with open(filepath) as f:
                data = json.load(f)
            result = validate_trug(data)
            assert result.valid, f"Validation failed for {filepath}: {result.errors}"


# AGENT claude SHALL DEFINE RECORD testresearchtoolchainintegration AS A RECORD test_suite.
class TestResearchToolchainIntegration:
    """Test that trugs_tools can support TRUGS_RESEARCH workflows."""

    # AGENT SHALL VALIDATE PROCESS test_knowledge_branch_generation.
    def test_knowledge_branch_generation(self):
        """Knowledge_v1 branch (merged living+knowledge+research) generates valid TRUGs."""
        for template in ["minimal", "complete"]:
            trug = generate_trug("knowledge_v1", template=template)
            result = validate_trug(trug)
            assert result.valid, f"knowledge/{template} failed: {result.errors}"

    # AGENT SHALL VALIDATE PROCESS test_trugs_validate_cli_available.
    def test_trugs_validate_cli_available(self):
        """trugs-validate CLI command is importable."""
        from trugs_tools.cli import validate_command
        assert callable(validate_command)

    # AGENT SHALL VALIDATE PROCESS test_trugs_render_cli_available.
    def test_trugs_render_cli_available(self):
        """trugs-render CLI command is importable."""
        from trugs_tools.cli import render_command
        assert callable(render_command)
