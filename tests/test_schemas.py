"""Tests for TRUGS branch schema loader and validator."""

import json
import os

import pytest

from trugs_tools.schemas import (
    get_branch_node_types,
    get_branch_relations,
    list_branch_schemas,
    load_branch_schema,
    validate_branch_schema,
)
from trugs_tools.generator import generate_trug

ALL_BRANCHES = [
    "web", "writer",
    "orchestration", "knowledge_v1",
    "nested",
    "project_tracking", "aaa",
]

# Branches that have generate_trug templates (excludes schema-only branches)
TEMPLATE_BRANCHES = [
    "web", "writer",
    "orchestration", "knowledge_v1",
    "nested",
]

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EXAMPLES")

# ── Schema Loading Tests ────────────────────────────────────────────────


@pytest.mark.parametrize("branch", ALL_BRANCHES)
def test_load_branch_schema(branch):
    """Each branch schema can be loaded."""
    schema = load_branch_schema(branch)
    assert isinstance(schema, dict)


def test_load_unknown_branch_raises():
    """Unknown branch raises ValueError."""
    with pytest.raises(ValueError, match="Unknown branch"):
        load_branch_schema("nonexistent")


def test_list_branch_schemas_returns_expected_count():
    """list_branch_schemas returns the expected number of items."""
    branches = list_branch_schemas()
    assert len(branches) == 7


def test_list_branch_schemas_contains_all():
    """list_branch_schemas contains every expected branch."""
    branches = list_branch_schemas()
    for b in ALL_BRANCHES:
        assert b in branches


def test_list_branch_schemas_excludes_old():
    """list_branch_schemas does NOT contain merged branches."""
    branches = list_branch_schemas()
    assert "living" not in branches
    assert "knowledge" not in branches
    assert "research" not in branches


@pytest.mark.parametrize("branch", ALL_BRANCHES)
def test_schema_has_required_keys(branch):
    """Each schema has branch, graph_type, node_types, relations."""
    schema = load_branch_schema(branch)
    for key in ("branch", "graph_type", "node_types", "relations"):
        assert key in schema, f"Schema '{branch}' missing key '{key}'"


# ── Node Type Tests ─────────────────────────────────────────────────────

EXPECTED_NODE_TYPES = {
    "web": ["SITE", "PAGE", "SECTION"],
    "writer": ["BOOK", "CHAPTER", "SECTION", "PARAGRAPH", "CITATION", "REFERENCE"],
    "orchestration": ["AGENT", "PRINCIPAL", "RESOURCE", "PERMISSION", "TASK", "ESCALATION"],
    "knowledge_v1": [
        "KNOWLEDGE_GRAPH", "CONCEPT", "ENTITY", "CLASS", "INSTANCE",
        "QUERY", "ANSWER", "SYNTHESIS", "DECISION", "TOOL_EXECUTION",
        "WEB_SOURCE", "PAPER", "PROJECT", "AUTHOR", "CLAIM", "VERSION",
    ],
    "nested": ["TASK", "SUBGRAPH", "RESULT"],
    "project_tracking": ["TRACKER", "EPIC", "TASK", "SUBTASK", "MILESTONE", "MOTIVATION", "PRINCIPLE"],
    "aaa": ["AAA", "PHASE", "TASK", "AUDIT", "RISK", "ADR", "DEPENDENCY", "RESEARCH_SOURCE", "QUALITY_GATE", "SUB_ISSUE"],
}


@pytest.mark.parametrize("branch", ALL_BRANCHES)
def test_get_branch_node_types(branch):
    """get_branch_node_types returns expected types for each branch."""
    actual = get_branch_node_types(branch)
    expected = EXPECTED_NODE_TYPES[branch]
    assert set(actual) == set(expected)


# ── Relation Tests ───────────────────────────────────────────────────────

EXPECTED_RELATIONS = {
    "web": ["contains", "links_to"],
    "writer": ["contains", "cites", "references", "continues", "supports", "contradicts"],
    "orchestration": [
        "contains", "delegates_to", "reports_to",
        "authorizes", "accesses", "escalates_to",
    ],
    "knowledge_v1": [
        "contains",
        "triggers", "produces", "synthesizes_to", "builds_on", "cites",
        "is_a", "has_property", "part_of", "causes", "related_to",
        "defines", "supports", "contradicts", "alternative_to",
        "deprecated_by", "depends_on", "authored_by",
        "rejects", "invalidates", "supersedes",
    ],
    "nested": ["contains", "precedes", "produces"],
    "project_tracking": [
        "CONTAINS", "DEPENDS_ON", "BLOCKS", "INFORMS",
        "GROUNDS", "EXTENDS", "COMPLETES", "TRACKS",
        "RESOLVES", "SUPERSEDES",
    ],
    "aaa": [
        "precedes", "depends_on", "blocked_by", "mitigates",
        "validates", "tracks", "cites", "decides",
        "implements", "audits",
    ],
}


@pytest.mark.parametrize("branch", ALL_BRANCHES)
def test_get_branch_relations(branch):
    """get_branch_relations returns expected relations for each branch."""
    actual = get_branch_relations(branch)
    expected = EXPECTED_RELATIONS[branch]
    assert set(actual) == set(expected)


# ── Schema Sync Tests (S4.2.5) ──────────────────────────────────────────

BRANCH_TEMPLATE_PAIRS = [
    (b, t) for b in TEMPLATE_BRANCHES for t in ("minimal", "complete")
]


@pytest.mark.parametrize("branch,template", BRANCH_TEMPLATE_PAIRS,
                         ids=[f"{b}-{t}" for b, t in BRANCH_TEMPLATE_PAIRS])
def test_generated_trug_validates_against_schema(branch, template):
    """Generated TRUGs from every branch×template pass schema validation."""
    trug = generate_trug(branch, template=template, validate=False)
    errors = validate_branch_schema(trug)
    assert errors == [], (
        f"Schema validation errors for {branch}/{template}: {errors}"
    )


def _get_all_example_json_paths():
    """Collect all .json files under EXAMPLES/."""
    paths = []
    for root, _dirs, files in os.walk(EXAMPLES_DIR):
        for fname in sorted(files):
            if fname.endswith(".json"):
                paths.append(os.path.join(root, fname))
    return sorted(paths)


_EXAMPLE_PATHS = _get_all_example_json_paths()

# Examples that use relations not yet in schemas (schema–example drift).
# These are tracked as known sync issues for S4.2.5.
_KNOWN_SCHEMA_DRIFT = {
    "knowledge/complex.json",
    "orchestration/complex.json",
    "orchestration/medium.json",
    "web/complex.json",
    "writer/complex.json",
    "writer/medium.json",
}


@pytest.mark.parametrize(
    "example_path", _EXAMPLE_PATHS,
    ids=[os.path.relpath(p, EXAMPLES_DIR) for p in _EXAMPLE_PATHS],
)
def test_example_validates_against_branch_schema(example_path):
    """Every example JSON file validates against its branch schema."""
    rel = os.path.relpath(example_path, EXAMPLES_DIR)
    if rel in _KNOWN_SCHEMA_DRIFT:
        pytest.xfail(f"Known schema–example drift: {rel}")
    with open(example_path, encoding="utf-8") as f:
        trug = json.load(f)
    errors = validate_branch_schema(trug)
    assert errors == [], (
        f"Schema errors in {rel}: {errors}"
    )


def test_all_examples_discovered():
    """Sanity check: we found at least 19 example JSON files."""
    assert len(_EXAMPLE_PATHS) >= 19


# ── Validation Tests ────────────────────────────────────────────────────


def test_validate_valid_trug_returns_empty():
    """A valid TRUG returns empty error list."""
    trug = generate_trug("web", template="minimal", validate=False)
    errors = validate_branch_schema(trug)
    assert errors == []


def test_validate_invalid_node_type():
    """An invalid node type produces an error."""
    trug = generate_trug("web", template="minimal", validate=False)
    trug["nodes"].append({
        "id": "bad_1",
        "type": "BOGUS_TYPE",
        "metric_level": "BASE_BOGUS_TYPE",
        "parent_id": None,
        "properties": {},
    })
    errors = validate_branch_schema(trug)
    assert len(errors) == 1
    assert "BOGUS_TYPE" in errors[0]


def test_validate_invalid_relation():
    """An invalid relation produces an error."""
    trug = generate_trug("web", template="minimal", validate=False)
    trug["edges"].append({
        "from_id": "module_1",
        "to_id": "func_1",
        "relation": "BOGUS_RELATION",
    })
    errors = validate_branch_schema(trug)
    assert len(errors) == 1
    assert "BOGUS_RELATION" in errors[0]


def test_validate_unknown_graph_type_returns_empty():
    """Unknown graph type returns empty list (graceful handling)."""
    trug = {
        "name": "test",
        "version": "1.0.0",
        "type": "UNKNOWN_TYPE",
        "nodes": [{"id": "n1", "type": "FOO", "metric_level": "BASE_FOO"}],
        "edges": [],
    }
    errors = validate_branch_schema(trug)
    assert errors == []


def test_validate_empty_type_returns_empty():
    """Empty type string returns empty list."""
    trug = {
        "name": "test",
        "version": "1.0.0",
        "type": "",
        "nodes": [{"id": "n1", "type": "FOO", "metric_level": "BASE_FOO"}],
        "edges": [],
    }
    errors = validate_branch_schema(trug)
    assert errors == []


# ── Migration Error Tests ────────────────────────────────────────────────


@pytest.mark.parametrize("old_branch", ["living", "knowledge", "research"])
def test_generate_old_branch_raises_migration_error(old_branch):
    """Old branch names raise ValueError with migration hint."""
    with pytest.raises(ValueError, match="knowledge_v1"):
        generate_trug(old_branch)


@pytest.mark.parametrize("old_branch", ["living", "knowledge", "research"])
def test_migration_error_includes_old_name(old_branch):
    """Migration error includes the old branch name the user tried."""
    with pytest.raises(ValueError, match=old_branch):
        generate_trug(old_branch)


# ── Thread Safety Tests ─────────────────────────────────────────────────


def test_concurrent_schema_loading():
    """Loading schemas concurrently never raises ValueError."""
    import concurrent.futures
    import trugs_tools.schemas as schemas_mod

    def load_branch(branch):
        return load_branch_schema(branch)

    # Clear the cache to force a fresh load race
    schemas_mod._schema_cache.clear()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        # Submit 100 concurrent loads across all branches
        futures = [
            pool.submit(load_branch, ALL_BRANCHES[i % len(ALL_BRANCHES)])
            for i in range(100)
        ]
        for fut in concurrent.futures.as_completed(futures):
            # Should never raise; every result must be a dict
            result = fut.result()
            assert isinstance(result, dict)
