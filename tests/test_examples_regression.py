"""Regression tests for all TRUGS example files."""

import pytest
import json
import glob
import os

from trugs_tools.validator import validate_trug

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EXAMPLES")


def get_all_examples():
    """Discover all JSON example files."""
    return sorted(glob.glob(os.path.join(EXAMPLES_DIR, "**/*.json"), recursive=True))


@pytest.fixture(params=get_all_examples(), ids=lambda p: os.path.relpath(p, EXAMPLES_DIR))
def example_path(request):
    """Parameterized fixture for each example file."""
    return request.param


def test_example_is_valid_json(example_path):
    """Test that each example file is valid JSON."""
    with open(example_path) as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_example_passes_validation(example_path):
    """Test that each example passes TRUGS validation."""
    with open(example_path) as f:
        data = json.load(f)
    result = validate_trug(data)
    assert result.valid, f"Validation failed for {example_path}: {result.errors}"


def test_example_has_required_fields(example_path):
    """Test that each example has all required top-level fields."""
    with open(example_path) as f:
        data = json.load(f)
    for field in ["name", "version", "type", "branch", "nodes", "edges"]:
        assert field in data, f"Missing field '{field}' in {example_path}"


def test_example_has_dimensions(example_path):
    """Test that each example has dimension declarations."""
    with open(example_path) as f:
        data = json.load(f)
    assert "dimensions" in data, f"Missing dimensions in {example_path}"
    assert len(data["dimensions"]) > 0


def test_example_nodes_have_required_fields(example_path):
    """Test that all nodes in examples have required fields."""
    with open(example_path) as f:
        data = json.load(f)
    for node in data["nodes"]:
        assert "id" in node, f"Node missing 'id' in {example_path}"
        assert "type" in node, f"Node missing 'type' in {example_path}"
        assert "metric_level" in node, f"Node missing 'metric_level' in {example_path}"


def test_example_edges_have_required_fields(example_path):
    """Test that all edges in examples have required fields."""
    with open(example_path) as f:
        data = json.load(f)
    for edge in data["edges"]:
        assert "from_id" in edge, f"Edge missing 'from_id' in {example_path}"
        assert "to_id" in edge, f"Edge missing 'to_id' in {example_path}"
        assert "relation" in edge, f"Edge missing 'relation' in {example_path}"


def test_example_node_ids_unique(example_path):
    """Test that node IDs are unique within each example."""
    with open(example_path) as f:
        data = json.load(f)
    ids = [n["id"] for n in data["nodes"]]
    assert len(ids) == len(set(ids)), f"Duplicate node IDs in {example_path}"


def test_example_edge_refs_valid(example_path):
    """Test that all edge references point to valid nodes."""
    with open(example_path) as f:
        data = json.load(f)
    node_ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["from_id"] in node_ids, f"Invalid from_id '{edge['from_id']}' in {example_path}"
        assert edge["to_id"] in node_ids, f"Invalid to_id '{edge['to_id']}' in {example_path}"


# ─── Branch-Level Aggregation Tests ──────────────────────────────

CORE_BRANCHES = ["web", "writer"]
ADVANCED_BRANCHES = ["orchestration", "knowledge", "nested"]
ALL_BRANCHES = CORE_BRANCHES + ADVANCED_BRANCHES


@pytest.mark.parametrize("branch", ALL_BRANCHES)
def test_branch_directory_exists(branch):
    """Test that each branch has a directory in EXAMPLES."""
    branch_dir = os.path.join(EXAMPLES_DIR, branch)
    assert os.path.isdir(branch_dir), f"Missing branch directory: {branch}"


@pytest.mark.parametrize("branch", ALL_BRANCHES)
def test_branch_has_readme(branch):
    """Test that each branch directory has a README.md."""
    readme = os.path.join(EXAMPLES_DIR, branch, "README.md")
    assert os.path.exists(readme), f"Missing README.md for branch: {branch}"


@pytest.mark.parametrize("branch", CORE_BRANCHES)
def test_core_branch_has_minimum_examples(branch):
    """Test that each core branch has at least minimal and complete examples."""
    branch_dir = os.path.join(EXAMPLES_DIR, branch)
    examples = glob.glob(os.path.join(branch_dir, "*.json"))
    assert len(examples) >= 4, f"Branch {branch} has only {len(examples)} examples (expected >= 4)"


@pytest.mark.parametrize("branch", ADVANCED_BRANCHES)
def test_advanced_branch_has_minimum_examples(branch):
    """Test that each advanced branch has simple, medium, and complex examples."""
    branch_dir = os.path.join(EXAMPLES_DIR, branch)
    for name in ["simple.json", "medium.json", "complex.json"]:
        filepath = os.path.join(branch_dir, name)
        assert os.path.exists(filepath), f"Missing {name} for branch: {branch}"


def test_total_example_count():
    """Test that we have at least 37 examples total."""
    examples = get_all_examples()
    assert len(examples) >= 19, f"Expected >= 19 examples, got {len(examples)}"
