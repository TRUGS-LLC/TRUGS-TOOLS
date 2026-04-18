"""Integration test harness for TRUGS Tools components.

Consolidates integration smoke tests for all TRUGS ecosystem components:
- PERAGO: AAA.md task orchestration (v1.0.0 COMPLETE)
- TRUGS_RESEARCH: Research graph validation (v1.0.0 DEPLOYED)
- TRUGS_GATEWAY: API gateway (VISION-phase, deferred)

This harness provides a single entry point for CI/CD integration validation.
"""

import pytest
import os
import sys

from trugs_tools import validate_trug, generate_trug, __version__
from trugs_tools.generator import SUPPORTED_BRANCHES
from trugs_tools.schemas import list_branch_schemas

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


# AGENT claude SHALL DEFINE RECORD testtoolchainsmoke AS A RECORD test_suite.
class TestToolchainSmoke:
    """Smoke tests for TRUGS_TOOLS core functionality."""

    # AGENT SHALL VALIDATE PROCESS test_version.
    def test_version(self):
        """Version is accessible and valid."""
        assert __version__ == "1.0.0"

    # AGENT SHALL VALIDATE PROCESS test_all_branches_generate.
    def test_all_branches_generate(self):
        """All 5 branches generate valid TRUGs."""
        assert len(SUPPORTED_BRANCHES) == 5
        for branch in SUPPORTED_BRANCHES:
            trug = generate_trug(branch, template="minimal")
            result = validate_trug(trug)
            assert result.valid, f"{branch} failed: {result.errors}"

    # AGENT SHALL VALIDATE PROCESS test_all_schemas_available.
    def test_all_schemas_available(self):
        """All branch schemas are loadable."""
        schemas = list_branch_schemas()
        assert len(schemas) >= 7

    # AGENT SHALL VALIDATE PROCESS test_generate_validate_roundtrip.
    def test_generate_validate_roundtrip(self):
        """Generate → validate roundtrip works for all branches."""
        for branch in SUPPORTED_BRANCHES:
            for template in ["minimal", "complete"]:
                trug = generate_trug(branch, template=template)
                result = validate_trug(trug)
                assert result.valid, f"{branch}/{template}: {result.errors}"


# AGENT claude SHALL DEFINE RECORD testperagointegrationsmoke AS A RECORD test_suite.
class TestPeragoIntegrationSmoke:
    """Smoke tests for PERAGO integration."""

    pytestmark = pytest.mark.skipif(
        not os.path.exists(os.path.join(REPO_ROOT, "PERAGO", "src")),
        reason="PERAGO not available",
    )

    # AGENT SHALL VALIDATE PROCESS test_perago_importable.
    def test_perago_importable(self):
        """PERAGO models are importable."""
        from src.models import TRUGNode, TRUGGraph
        assert TRUGNode is not None
        assert TRUGGraph is not None

    # AGENT SHALL VALIDATE PROCESS test_trugs_tools_generates_perago_compatible_data.
    def test_trugs_tools_generates_perago_compatible_data(self):
        """Generated TRUGs contain fields compatible with PERAGO models."""
        trug = generate_trug("web", template="minimal")
        for node in trug["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "properties" in node


# AGENT claude SHALL DEFINE RECORD testtrugsresearchintegrationsmoke AS A RECORD test_suite.
class TestTrugsResearchIntegrationSmoke:
    """Smoke tests for TRUGS_RESEARCH integration."""

    pytestmark = pytest.mark.skipif(
        not os.path.exists(os.path.join(REPO_ROOT, "TRUGS_RESEARCH")),
        reason="TRUGS_RESEARCH not available",
    )

    # AGENT SHALL VALIDATE PROCESS test_trugs_research_exists.
    def test_trugs_research_exists(self):
        """TRUGS_RESEARCH directory exists."""
        assert os.path.isdir(os.path.join(REPO_ROOT, "TRUGS_RESEARCH"))

    # AGENT SHALL VALIDATE PROCESS test_knowledge_branch_works.
    def test_knowledge_branch_works(self):
        """Knowledge_v1 branch (merged living+knowledge+research) generates valid TRUGs."""
        trug = generate_trug("knowledge_v1", template="complete")
        result = validate_trug(trug)
        assert result.valid


# AGENT claude SHALL DEFINE RECORD testtrugsgatewayintegrationsmoke AS A RECORD test_suite.
class TestTrugsGatewayIntegrationSmoke:
    """Stub for TRUGS_GATEWAY integration tests.

    TRUGS_GATEWAY is currently in VISION-phase only (no implementation).
    These tests will be enabled when TRUGS_GATEWAY has code to test.
    """

    pytestmark = pytest.mark.skipif(
        not os.path.exists(os.path.join(REPO_ROOT, "TRUGS_GATEWAY", "src")),
        reason="TRUGS_GATEWAY implementation not available (VISION-phase only)",
    )

    # AGENT SHALL VALIDATE PROCESS test_gateway_placeholder.
    def test_gateway_placeholder(self):
        """Placeholder for future TRUGS_GATEWAY integration tests."""
        pytest.skip("TRUGS_GATEWAY not yet implemented")
