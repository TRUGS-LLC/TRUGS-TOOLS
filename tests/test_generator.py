"""Tests for TRUGS generator."""

import pytest
import json

from trugs_tools.generator import generate_trug, SUPPORTED_BRANCHES
from trugs_tools.validator import validate_trug


# AGENT SHALL VALIDATE PROCESS test_generate_web_minimal.
def test_generate_web_minimal():
    """Test generating minimal Web TRUG."""
    trug = generate_trug("web", template="minimal")
    
    assert trug["name"] == "Web Minimal Example"
    assert trug["type"] == "WEB"
    assert trug["branch"] == "web"
    assert len(trug["nodes"]) == 3
    assert len(trug["edges"]) == 2


# AGENT SHALL VALIDATE PROCESS test_generate_web_complete.
def test_generate_web_complete():
    """Test generating complete Web TRUG."""
    trug = generate_trug("web", template="complete")
    
    assert trug["name"] == "Web Complete Example"
    assert trug["type"] == "WEB"
    assert trug["branch"] == "web"
    assert len(trug["nodes"]) > 5
    assert len(trug["edges"]) > 5


# AGENT SHALL VALIDATE PROCESS test_generate_web_with_extensions.
def test_generate_web_with_extensions():
    """Test generating Web TRUG with extensions."""
    trug = generate_trug("web", extensions=["typed", "scoped"])
    
    assert trug is not None
    assert trug.get("extensions") == ["typed", "scoped"]


# AGENT SHALL VALIDATE PROCESS test_generated_trug_validates.
def test_generated_trug_validates():
    """Test that generated TRUGs pass validation."""
    for branch in SUPPORTED_BRANCHES:
        trug = generate_trug(branch, template="minimal", validate=False)
        result = validate_trug(trug)
        
        assert result.valid, f"Generated {branch} TRUG failed validation: {result.errors}"


# AGENT SHALL VALIDATE PROCESS test_generated_complete_trug_validates.
def test_generated_complete_trug_validates():
    """Test that generated complete TRUGs pass validation."""
    for branch in SUPPORTED_BRANCHES:
        templates = SUPPORTED_BRANCHES[branch]
        if "complete" in templates:
            trug = generate_trug(branch, template="complete", validate=False)
            result = validate_trug(trug)
            
            assert result.valid, f"Generated complete {branch} TRUG failed validation"


# AGENT SHALL VALIDATE PROCESS test_generate_invalid_branch.
def test_generate_invalid_branch():
    """Test that invalid branch raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported branch"):
        generate_trug("invalid_branch")


# AGENT SHALL VALIDATE PROCESS test_generate_invalid_template.
def test_generate_invalid_template():
    """Test that invalid template raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported template"):
        generate_trug("web", template="invalid_template")


# AGENT SHALL VALIDATE PROCESS test_generate_with_validation_enabled.
def test_generate_with_validation_enabled():
    """Test that validation runs when enabled."""
    # Should succeed
    trug = generate_trug("web", validate=True)
    assert trug is not None


# AGENT SHALL VALIDATE PROCESS test_generate_validates_by_default.
def test_generate_validates_by_default():
    """Test that validation is enabled by default."""
    trug = generate_trug("web")
    assert trug is not None


# AGENT SHALL VALIDATE PROCESS test_generated_trug_has_required_fields.
def test_generated_trug_has_required_fields():
    """Test that generated TRUGs have all required fields."""
    trug = generate_trug("web")
    
    # Check root fields
    assert "name" in trug
    assert "version" in trug
    assert "type" in trug
    assert "nodes" in trug
    assert "edges" in trug
    
    # Check node fields
    for node in trug["nodes"]:
        assert "id" in node
        assert "type" in node
        assert "metric_level" in node


# AGENT SHALL VALIDATE PROCESS test_generated_trug_has_consistent_hierarchy.
def test_generated_trug_has_consistent_hierarchy():
    """Test that generated TRUGs have consistent parent/contains relationships."""
    trug = generate_trug("web", template="complete")
    
    # Build maps
    parent_map = {}  # child_id -> parent_id
    contains_map = {}  # parent_id -> [child_ids]
    
    for node in trug["nodes"]:
        if node.get("parent_id"):
            parent_map[node["id"]] = node["parent_id"]
    
    for edge in trug["edges"]:
        if edge["relation"] == "contains":
            parent_id = edge["from_id"]
            child_id = edge["to_id"]
            if parent_id not in contains_map:
                contains_map[parent_id] = []
            contains_map[parent_id].append(child_id)
    
    # Verify consistency
    for child_id, parent_id in parent_map.items():
        assert parent_id in contains_map, f"Parent {parent_id} missing contains edge"
        assert child_id in contains_map[parent_id], f"Child {child_id} not in parent's contains"


# AGENT SHALL VALIDATE PROCESS test_generated_trug_node_ids_unique.
def test_generated_trug_node_ids_unique():
    """Test that generated TRUGs have unique node IDs."""
    trug = generate_trug("web", template="complete")
    
    node_ids = [node["id"] for node in trug["nodes"]]
    assert len(node_ids) == len(set(node_ids)), "Duplicate node IDs found"


# AGENT SHALL VALIDATE PROCESS test_generated_trug_edges_reference_valid_nodes.
def test_generated_trug_edges_reference_valid_nodes():
    """Test that generated TRUGs edges reference existing nodes."""
    trug = generate_trug("web", template="complete")
    
    node_ids = {node["id"] for node in trug["nodes"]}
    
    for edge in trug["edges"]:
        assert edge["from_id"] in node_ids, f"Invalid from_id: {edge['from_id']}"
        assert edge["to_id"] in node_ids, f"Invalid to_id: {edge['to_id']}"


# AGENT SHALL VALIDATE PROCESS test_generated_trug_has_dimensions.
def test_generated_trug_has_dimensions():
    """Test that generated TRUGs have dimension declarations."""
    trug = generate_trug("web")
    
    assert "dimensions" in trug
    assert len(trug["dimensions"]) > 0
    
    for dimension in trug["dimensions"]:
        assert "name" in dimension
        assert "levels" in dimension


# AGENT SHALL VALIDATE PROCESS test_generated_trug_json_serializable.
def test_generated_trug_json_serializable():
    """Test that generated TRUGs are JSON serializable."""
    trug = generate_trug("web", template="complete")
    
    # Should not raise
    json_str = json.dumps(trug)
    assert json_str is not None
    
    # Should round-trip
    parsed = json.loads(json_str)
    assert parsed == trug


# AGENT SHALL VALIDATE PROCESS test_web_minimal_structure.
def test_web_minimal_structure():
    """Test Web minimal template has expected structure."""
    trug = generate_trug("web", template="minimal")
    
    # Should have site -> page -> section
    node_types = [node["type"] for node in trug["nodes"]]
    assert "SITE" in node_types
    assert "PAGE" in node_types
    assert "SECTION" in node_types


# AGENT SHALL VALIDATE PROCESS test_web_complete_structure.
def test_web_complete_structure():
    """Test Web complete template has expected structure."""
    trug = generate_trug("web", template="complete")
    
    # Should have various node types
    node_types = [node["type"] for node in trug["nodes"]]
    assert "SITE" in node_types
    assert "PAGE" in node_types


# AGENT SHALL VALIDATE PROCESS test_generate_to_file.
def test_generate_to_file(tmp_path):
    """Test generating TRUG to file."""
    from trugs_tools.generator import generate_to_file
    
    output_file = tmp_path / "test.json"
    generate_to_file(
        str(output_file),
        branch="web",
        template="minimal"
    )
    
    assert output_file.exists()
    
    # Load and validate
    with open(output_file) as f:
        trug = json.load(f)
    
    result = validate_trug(trug)
    assert result.valid


# ─── S1.3.3: Generator Edge Case Tests ────────────────────────────────


# AGENT SHALL VALIDATE PROCESS test_generate_branch_with_extensions.
def test_generate_branch_with_extensions():
    """Test branch with extensions adds extensions key."""
    trug = generate_trug("writer", extensions=["typed", "scoped"])

    assert trug is not None
    assert trug.get("extensions") == ["typed", "scoped"]
    assert trug["branch"] == "writer"


# AGENT SHALL VALIDATE PROCESS test_generate_validation_failure_during_generation.
def test_generate_validation_failure_during_generation():
    """Test validation failure during generation with mocked invalid output."""
    from unittest.mock import patch

    # AGENT claude SHALL DEFINE FUNCTION broken_generator.
    def broken_generator():
        return {
            "name": "Broken",
            "version": "1.0.0",
            "type": "CODE",
            "nodes": [
                {"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE"},
                {"id": "n1", "type": "FUNCTION", "metric_level": "BASE_FUNCTION"}  # duplicate
            ],
            "edges": [],
            "branch": "web"
        }

    with patch.dict(
        "trugs_tools.generator.SUPPORTED_BRANCHES",
        {"web": {"minimal": broken_generator, "complete": broken_generator}}
    ):
        with pytest.raises(RuntimeError, match="failed validation"):
            generate_trug("web", template="minimal", validate=True)


# ─── Sprint 3: Advanced Branch Generator Tests ────────────────────────


# AGENT SHALL VALIDATE PROCESS test_generate_advanced_branch_minimal.
@pytest.mark.parametrize("branch", ["orchestration", "knowledge_v1", "nested"])
def test_generate_advanced_branch_minimal(branch):
    """Test generating minimal TRUG for advanced branches."""
    trug = generate_trug(branch, template="minimal")
    assert trug["branch"] == branch
    assert len(trug["nodes"]) >= 3
    assert len(trug["edges"]) >= 2


# AGENT SHALL VALIDATE PROCESS test_generate_advanced_branch_complete.
@pytest.mark.parametrize("branch", ["orchestration", "knowledge_v1", "nested"])
def test_generate_advanced_branch_complete(branch):
    """Test generating complete TRUG for advanced branches."""
    trug = generate_trug(branch, template="complete")
    assert trug["branch"] == branch
    assert len(trug["nodes"]) >= 7


# AGENT SHALL VALIDATE PROCESS test_advanced_branch_validates.
@pytest.mark.parametrize("branch", ["orchestration", "knowledge_v1", "nested"])
def test_advanced_branch_validates(branch):
    """Test that advanced branch TRUGs pass validation."""
    for template in ["minimal", "complete"]:
        trug = generate_trug(branch, template=template, validate=False)
        result = validate_trug(trug)
        assert result.valid, f"{branch}/{template} failed: {result.errors}"


# AGENT SHALL VALIDATE PROCESS test_advanced_branch_has_dimensions.
@pytest.mark.parametrize("branch", ["orchestration", "knowledge_v1", "nested"])
def test_advanced_branch_has_dimensions(branch):
    """Test that advanced branches have dimension declarations."""
    trug = generate_trug(branch, template="minimal")
    assert "dimensions" in trug
    assert len(trug["dimensions"]) > 0


# AGENT SHALL VALIDATE PROCESS test_advanced_branch_node_ids_unique.
@pytest.mark.parametrize("branch", ["orchestration", "knowledge_v1", "nested"])
def test_advanced_branch_node_ids_unique(branch):
    """Test that advanced branches have unique node IDs."""
    trug = generate_trug(branch, template="complete")
    ids = [n["id"] for n in trug["nodes"]]
    assert len(ids) == len(set(ids))


# AGENT SHALL VALIDATE PROCESS test_advanced_branch_hierarchy_consistent.
@pytest.mark.parametrize("branch", ["orchestration", "knowledge_v1", "nested"])
def test_advanced_branch_hierarchy_consistent(branch):
    """Test parent/contains consistency for advanced branches."""
    trug = generate_trug(branch, template="complete")
    parent_map = {}
    for node in trug["nodes"]:
        if node.get("parent_id"):
            parent_map[node["id"]] = node["parent_id"]
    contains = {}
    for edge in trug["edges"]:
        if edge["relation"] == "contains":
            contains.setdefault(edge["from_id"], []).append(edge["to_id"])
    for child_id, parent_id in parent_map.items():
        assert parent_id in contains, f"Parent {parent_id} has no contains edges"
        assert child_id in contains[parent_id], f"Child {child_id} not in parent's contains"


# AGENT SHALL VALIDATE PROCESS test_supported_branches_count.
def test_supported_branches_count():
    """Test that we support all 5 branches (3 merged into knowledge_v1)."""
    assert len(SUPPORTED_BRANCHES) == 5


# AGENT SHALL VALIDATE PROCESS test_all_branches_have_minimal_and_complete.
def test_all_branches_have_minimal_and_complete():
    """Test that every branch supports both minimal and complete templates."""
    for branch_name, templates in SUPPORTED_BRANCHES.items():
        assert "minimal" in templates, f"Branch {branch_name} missing minimal template"
        assert "complete" in templates, f"Branch {branch_name} missing complete template"
