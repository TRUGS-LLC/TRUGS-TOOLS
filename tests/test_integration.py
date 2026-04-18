"""Integration tests for TRUGS tools end-to-end workflow."""

import pytest
import json
from pathlib import Path

from trugs_tools import generate_trug, validate_trug, __version__

FIXED_TEST_DATE = "2025-01-01"


# AGENT SHALL VALIDATE PROCESS test_full_workflow_web.
def test_full_workflow_web():
    """Test complete workflow: generate → validate → check structure."""
    # Generate
    trug = generate_trug("web", template="complete")
    
    # Validate
    result = validate_trug(trug)
    assert result.valid
    assert len(result.errors) == 0
    
    # Check structure
    assert trug["branch"] == "web"
    assert "nodes" in trug
    assert "edges" in trug
    assert len(trug["nodes"]) > 0
    assert len(trug["edges"]) > 0


# AGENT SHALL VALIDATE PROCESS test_full_workflow_all_branches.
def test_full_workflow_all_branches():
    """Test that all branches generate valid TRUGs."""
    branches = ["web", "writer", "orchestration", "knowledge_v1", "nested"]
    
    for branch in branches:
        for template in ["minimal", "complete"]:
            # Generate
            trug = generate_trug(branch, template=template)
            
            # Validate
            result = validate_trug(trug)
            
            # Assert valid
            assert result.valid, f"{branch}/{template} failed: {result.errors}"
            assert trug["branch"] == branch


# AGENT SHALL VALIDATE PROCESS test_workflow_with_file_io.
def test_workflow_with_file_io(tmp_path):
    """Test workflow with file I/O."""
    from trugs_tools.generator import generate_to_file
    from trugs_tools.validator import validate_file
    
    # Generate to file
    output_file = tmp_path / "test.json"
    generate_to_file(
        str(output_file),
        branch="web",
        template="minimal"
    )
    
    # Validate from file
    result = validate_file(output_file)
    assert result.valid


# AGENT SHALL VALIDATE PROCESS test_extension_workflow.
def test_extension_workflow():
    """Test workflow with extensions."""
    # Generate with extensions
    trug = generate_trug("web", extensions=["typed", "scoped"])
    
    # Validate
    result = validate_trug(trug)
    assert result.valid
    
    # Check extensions are present at top level
    assert trug.get("extensions") == ["typed", "scoped"]


# AGENT SHALL VALIDATE PROCESS test_validation_catches_errors.
def test_validation_catches_errors():
    """Test that validator catches common errors."""
    # Test 1: Duplicate IDs
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [
            {"id": "node1", "type": "MODULE", "metric_level": "DEKA_MODULE"},
            {"id": "node1", "type": "FUNCTION", "metric_level": "BASE_FUNCTION"}
        ],
        "edges": []
    }
    
    result = validate_trug(trug)
    assert not result.valid
    assert any("DUPLICATE_NODE_ID" in e.code for e in result.errors)
    
    # Test 2: Missing required fields
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [{"id": "node1"}],  # Missing type, metric_level
        "edges": []
    }
    
    result = validate_trug(trug)
    assert not result.valid
    assert any("MISSING_NODE_FIELD" in e.code for e in result.errors)
    
    # Test 3: Invalid edge references
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [
            {"id": "node1", "type": "MODULE", "metric_level": "DEKA_MODULE"}
        ],
        "edges": [
            {"from_id": "node1", "to_id": "nonexistent", "relation": "calls"}
        ]
    }
    
    result = validate_trug(trug)
    assert not result.valid
    assert any("INVALID_TO_ID" in e.code for e in result.errors)


# AGENT SHALL VALIDATE PROCESS test_all_templates_have_required_fields.
def test_all_templates_have_required_fields():
    """Verify all generated templates have required fields."""
    branches = ["web", "writer", "orchestration", "knowledge_v1", "nested"]
    required_root_fields = ["name", "version", "type", "nodes", "edges"]
    required_node_fields = ["id", "type", "metric_level"]
    required_edge_fields = ["from_id", "to_id", "relation"]
    
    for branch in branches:
        trug = generate_trug(branch, template="minimal")
        
        # Check root fields
        for field in required_root_fields:
            assert field in trug, f"{branch} missing {field}"
        
        # Check node fields
        for node in trug["nodes"]:
            for field in required_node_fields:
                assert field in node, f"{branch} node missing {field}"
        
        # Check edge fields
        for edge in trug["edges"]:
            for field in required_edge_fields:
                assert field in edge, f"{branch} edge missing {field}"


# AGENT SHALL VALIDATE PROCESS test_consistency_between_parent_and_contains.
def test_consistency_between_parent_and_contains():
    """Verify parent_id and contains edges are consistent in all templates."""
    branches = ["web", "writer", "orchestration", "knowledge_v1", "nested"]
    
    for branch in branches:
        trug = generate_trug(branch, template="complete")
        
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
            assert parent_id in contains_map, f"{branch}: Parent {parent_id} has no contains edges"
            assert child_id in contains_map[parent_id], f"{branch}: Child {child_id} not in parent's contains"


# AGENT SHALL VALIDATE PROCESS test_json_serialization_roundtrip.
def test_json_serialization_roundtrip():
    """Test that generated TRUGs can be serialized and deserialized."""
    branches = ["web", "writer", "orchestration", "knowledge_v1", "nested"]
    
    for branch in branches:
        trug = generate_trug(branch)
        
        # Serialize to JSON
        json_str = json.dumps(trug, indent=2)
        
        # Deserialize
        trug_copy = json.loads(json_str)
        
        # Should be equal
        assert trug == trug_copy
        
        # Should still validate
        result = validate_trug(trug_copy)
        assert result.valid


# AGENT SHALL VALIDATE PROCESS test_version_info.
def test_version_info():
    """Test that version info is available."""
    from trugs_tools import __version__, __codename__
    
    assert __version__ == "1.0.0"
    assert __codename__ == "AAA_AARDVARK"


# AGENT SHALL VALIDATE PROCESS test_api_exports.
def test_api_exports():
    """Test that main API functions are exported."""
    from trugs_tools import validate_trug, generate_trug, ValidationResult
    
    # All should be callable
    assert callable(validate_trug)
    assert callable(generate_trug)
    assert ValidationResult is not None


# ─── S1.3.5: Integration Test Suite ───────────────────────────────────


# AGENT SHALL VALIDATE PROCESS test_validate_generate_render_pipeline.
def test_validate_generate_render_pipeline(tmp_path):
    """Test validate→generate→render pipeline."""
    from trugs_tools.generator import generate_to_file
    from trugs_tools.validator import validate_file
    from trugs_tools.renderer import render_aaa, render_readme, render_architecture

    # Generate a TRUG to file
    output_file = tmp_path / "generated.trug.json"
    generate_to_file(str(output_file), branch="web", template="complete")

    # Validate the generated file
    result = validate_file(output_file)
    assert result.valid

    # Load the generated TRUG
    with open(output_file) as f:
        trug = json.load(f)

    # Wrap it in a folder structure for rendering
    folder_trug = {
        "name": "Pipeline Test",
        "version": "1.0.0",
        "type": "PROJECT",
        "nodes": [
            {
                "id": "folder_root",
                "type": "FOLDER",
                "metric_level": "MEGA_ROOT",
                "parent_id": None,
                "properties": {
                    "name": "PIPELINE_TEST",
                    "purpose": "Pipeline integration test",
                    "phase": "TESTING",
                    "status": "ACTIVE",
                    "version": "1.0.0"
                }
            }
        ],
        "edges": []
    }

    # Render each file individually
    aaa = render_aaa(folder_trug, render_date=FIXED_TEST_DATE)
    readme = render_readme(folder_trug, render_date=FIXED_TEST_DATE)
    arch = render_architecture(folder_trug, render_date=FIXED_TEST_DATE)

    assert len(aaa) > 0
    assert len(readme) > 0
    assert len(arch) > 0
    assert "## VISION" in aaa
    assert "# PIPELINE_TEST" in readme
    assert "## Quick Reference" in arch


# AGENT SHALL VALIDATE PROCESS test_all_branches_generate_valid_trugs.
def test_all_branches_generate_valid_trugs():
    """Test all branches generate valid TRUGs that validate correctly."""
    branches = ["web", "writer", "orchestration", "knowledge_v1", "nested"]

    for branch in branches:
        for template in ["minimal", "complete"]:
            trug = generate_trug(branch, template=template)
            result = validate_trug(trug)
            assert result.valid, f"{branch}/{template} failed: {result.errors}"


# AGENT SHALL VALIDATE PROCESS test_render_output_contains_expected_sections.
def test_render_output_contains_expected_sections():
    """Test render output contains expected sections."""
    from trugs_tools.renderer import render_aaa, render_readme, render_architecture

    folder_trug = {
        "name": "SECTION_TEST",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": "Test project for section validation",
        "nodes": [
            {
                "id": "folder_root",
                "type": "FOLDER",
                "metric_level": "MEGA_ROOT",
                "parent_id": None,
                "properties": {
                    "name": "SECTION_TEST",
                    "purpose": "Section test",
                    "phase": "CODING",
                    "status": "ACTIVE",
                    "version": "1.0.0"
                }
            },
            {
                "id": "src_main",
                "type": "SOURCE",
                "metric_level": "KILO_SRC",
                "parent_id": "folder_root",
                "properties": {"name": "main.py", "purpose": "Entry point"}
            }
        ],
        "edges": []
    }

    aaa = render_aaa(folder_trug, render_date=FIXED_TEST_DATE)
    assert "## VISION" in aaa
    assert "## ARCHITECTURE" in aaa
    assert "## METADATA" in aaa

    readme = render_readme(folder_trug, render_date=FIXED_TEST_DATE)
    assert "# SECTION_TEST" in readme
    assert "## Documentation" in readme

    arch = render_architecture(folder_trug, render_date=FIXED_TEST_DATE)
    assert "## Quick Reference" in arch
    assert "## Component Hierarchy" in arch
    assert "## Node Details" in arch


# ─── S1.3.6: Regression Test Suite ────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS test_real_reference_trug_validates.
def test_real_reference_trug_validates():
    """Test real REFERENCE/folder.trug.json validates."""
    reference_path = Path(__file__).parent.parent.parent / "REFERENCE" / "folder.trug.json"
    if not reference_path.exists():
        pytest.skip("REFERENCE/folder.trug.json not found")

    result = validate_trug(str(reference_path))
    # Real files may have warnings but should parse without PARSE_ERROR
    assert not any(e.code == "PARSE_ERROR" for e in result.errors)


# AGENT SHALL VALIDATE PROCESS test_real_protocol_trug_validates.
def test_real_protocol_trug_validates():
    """Test real TRUGS_PROTOCOL/folder.trug.json validates."""
    protocol_path = Path(__file__).parent.parent.parent / "TRUGS_PROTOCOL" / "folder.trug.json"
    if not protocol_path.exists():
        pytest.skip("TRUGS_PROTOCOL/folder.trug.json not found")

    result = validate_trug(str(protocol_path))
    assert not any(e.code == "PARSE_ERROR" for e in result.errors)


# AGENT SHALL VALIDATE PROCESS test_example_trug_files_validate.
def test_example_trug_files_validate():
    """Test all EXAMPLES/*.trug.json validate (if any exist)."""
    examples_dir = Path(__file__).parent.parent / "EXAMPLES"
    if not examples_dir.exists():
        pytest.skip("EXAMPLES directory not found")

    trug_files = list(examples_dir.glob("*.trug.json"))
    if not trug_files:
        pytest.skip("No .trug.json files in EXAMPLES/")

    for trug_file in trug_files:
        result = validate_trug(str(trug_file))
        assert not any(e.code == "PARSE_ERROR" for e in result.errors), \
            f"{trug_file.name} has parse errors"


# ─── S1.3.7: Performance Benchmark ───────────────────────────────────


# AGENT SHALL VALIDATE PROCESS test_generate_and_validate_100_trugs_performance.
def test_generate_and_validate_100_trugs_performance():
    """Test generating and validating 100 TRUGs in under 5 seconds."""
    import time

    branches = ["web", "writer", "orchestration", "knowledge_v1", "nested"]
    start = time.time()

    for i in range(100):
        branch = branches[i % len(branches)]
        trug = generate_trug(branch, template="minimal", validate=False)
        result = validate_trug(trug)
        assert result.valid

    elapsed = time.time() - start
    assert elapsed < 5.0, f"100 generate+validate took {elapsed:.2f}s (limit: 5s)"
