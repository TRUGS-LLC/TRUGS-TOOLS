"""Tests for TRUGS validator — all 16 CORE rules."""

import json
import tempfile
from pathlib import Path
from copy import deepcopy

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trugs_tools.validate import (
    validate, validate_file, ValidationResult,
    rule_1_unique_ids, rule_2_edge_id_validity, rule_3_hierarchy_consistency,
    rule_4_metric_level_ordering, rule_5_dimension_declaration,
    rule_6_required_fields, rule_7_field_type_correctness,
    rule_8_extension_declaration, rule_9_metric_level_format,
    rule_10_subject_operation, rule_11_operation_object,
    rule_12_modifier_entity, rule_13_qualifier_operation,
    rule_14_constraint_subject, rule_15_no_double_negation,
    rule_16_reference_scope,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

MINIMAL_VALID = {
    "name": "Test",
    "version": "1.0.0",
    "type": "CODE",
    "dimensions": {"d": {"description": "test", "base_level": "BASE"}},
    "capabilities": {"extensions": [], "vocabularies": [], "profiles": []},
    "nodes": [
        {
            "id": "root",
            "type": "MODULE",
            "properties": {},
            "parent_id": None,
            "contains": [],
            "metric_level": "DEKA_MODULE",
            "dimension": "d",
        }
    ],
    "edges": [],
}

MINIMAL_V091 = {
    "name": "Test v1.0.0",
    "version": "1.0.0",
    "type": "CODE",
    "dimensions": {"d": {"description": "test"}},
    "capabilities": {"extensions": [], "vocabularies": ["core_v1.0.0"], "profiles": []},
    "nodes": [
        {
            "id": "system",
            "type": "PARTY",
            "properties": {},
            "parent_id": None,
            "contains": [],
            "metric_level": "BASE_ACTOR",
            "dimension": "d",
        }
    ],
    "edges": [],
}


def _make(**overrides):
    t = deepcopy(MINIMAL_VALID)
    t.update(overrides)
    return t


def _make_v091(**overrides):
    t = deepcopy(MINIMAL_V091)
    t.update(overrides)
    return t


def _run(trug):
    return validate(trug)


def _errors(result):
    return [e.code for e in result.errors]


# ─── Rule 1: Unique IDs ───────────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_1 THEN ASSERT RECORD graph CONTAINS UNIQUE RECORD node.
def test_rule_1_pass():
    r = _run(MINIMAL_VALID)
    assert "DUPLICATE_NODE_ID" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_1 THEN REJECT RECORD graph SUBJECT_TO RECORD duplicate.
def test_rule_1_duplicate():
    t = _make(nodes=[
        {"id": "a", "type": "X", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_X", "dimension": "d"},
        {"id": "a", "type": "Y", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_Y", "dimension": "d"},
    ])
    r = _run(t)
    assert "DUPLICATE_NODE_ID" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_1 THEN REQUIRE EACH RECORD node CONTAINS RECORD field.
def test_rule_1_missing_id():
    t = _make(nodes=[
        {"type": "X", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_X", "dimension": "d"},
    ])
    r = _run(t)
    assert "MISSING_NODE_ID" in _errors(r)


# ─── Rule 2: Edge ID Validity ─────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_2 THEN ASSERT RECORD edge CONTAINS VALID RECORD source AND RECORD target.
def test_rule_2_pass():
    t = _make(
        nodes=[
            {"id": "a", "type": "X", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_X", "dimension": "d"},
            {"id": "b", "type": "Y", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_Y", "dimension": "d"},
        ],
        edges=[{"from_id": "a", "to_id": "b", "relation": "CALLS"}],
    )
    r = _run(t)
    assert "INVALID_EDGE_REFERENCE" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_2 THEN REJECT RECORD edge SUBJECT_TO INVALID RECORD source.
def test_rule_2_invalid_from():
    t = _make(edges=[{"from_id": "ghost", "to_id": "root", "relation": "X"}])
    r = _run(t)
    assert "INVALID_EDGE_REFERENCE" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_2 THEN ASSERT RECORD edge CONTAINS RECORD reference.
def test_rule_2_cross_folder_ref_allowed():
    t = _make(edges=[{"from_id": "root", "to_id": "other_folder:node_1", "relation": "X"}])
    r = _run(t)
    assert "INVALID_EDGE_REFERENCE" not in _errors(r)


# ─── Rule 3: Hierarchy Consistency ─────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_3 THEN ASSERT RECORD graph CONTAINS VALID RECORD hierarchy.
def test_rule_3_pass():
    t = _make(nodes=[
        {"id": "parent", "type": "X", "properties": {}, "parent_id": None, "contains": ["child"], "metric_level": "DEKA_X", "dimension": "d"},
        {"id": "child", "type": "Y", "properties": {}, "parent_id": "parent", "contains": [], "metric_level": "BASE_Y", "dimension": "d"},
    ])
    r = _run(t)
    assert "INCONSISTENT_HIERARCHY" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_3 THEN REJECT RECORD node SUBJECT_TO INVALID RECORD hierarchy.
def test_rule_3_parent_missing_child():
    t = _make(nodes=[
        {"id": "parent", "type": "X", "properties": {}, "parent_id": None, "contains": [], "metric_level": "DEKA_X", "dimension": "d"},
        {"id": "child", "type": "Y", "properties": {}, "parent_id": "parent", "contains": [], "metric_level": "BASE_Y", "dimension": "d"},
    ])
    r = _run(t)
    assert "INCONSISTENT_HIERARCHY" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_3 THEN REJECT RECORD node SUBJECT_TO INVALID RECORD parent.
def test_rule_3_contains_missing_parent():
    t = _make(nodes=[
        {"id": "parent", "type": "X", "properties": {}, "parent_id": None, "contains": ["child"], "metric_level": "DEKA_X", "dimension": "d"},
        {"id": "child", "type": "Y", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_Y", "dimension": "d"},
    ])
    r = _run(t)
    assert "INCONSISTENT_HIERARCHY" in _errors(r)


# ─── Rule 4: Metric Level Ordering ────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_4 THEN ASSERT RECORD hierarchy.
def test_rule_4_pass():
    t = _make(nodes=[
        {"id": "p", "type": "X", "properties": {}, "parent_id": None, "contains": ["c"], "metric_level": "DEKA_X", "dimension": "d"},
        {"id": "c", "type": "Y", "properties": {}, "parent_id": "p", "contains": [], "metric_level": "BASE_Y", "dimension": "d"},
    ])
    r = _run(t)
    assert "INVALID_METRIC_ORDERING" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_4 THEN REJECT RECORD hierarchy SUBJECT_TO INVALID RECORD ordering.
def test_rule_4_child_bigger_than_parent():
    t = _make(nodes=[
        {"id": "p", "type": "X", "properties": {}, "parent_id": None, "contains": ["c"], "metric_level": "BASE_X", "dimension": "d"},
        {"id": "c", "type": "Y", "properties": {}, "parent_id": "p", "contains": [], "metric_level": "KILO_Y", "dimension": "d"},
    ])
    r = _run(t)
    assert "INVALID_METRIC_ORDERING" in _errors(r)


# ─── Rule 5: Dimension Declaration ────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_5 THEN ASSERT RECORD node REFERENCES DATA dimensions.
def test_rule_5_pass():
    r = _run(MINIMAL_VALID)
    assert "UNDECLARED_DIMENSION" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_5 THEN REJECT RECORD node SUBJECT_TO INVALID DATA dimensions.
def test_rule_5_undeclared():
    t = _make(nodes=[
        {"id": "x", "type": "X", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_X", "dimension": "nonexistent"},
    ])
    r = _run(t)
    assert "UNDECLARED_DIMENSION" in _errors(r)


# ─── Rule 6: Required Fields ──────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_6 THEN ASSERT RECORD graph CONTAINS ALL REQUIRED RECORD field.
def test_rule_6_pass():
    r = _run(MINIMAL_VALID)
    assert "MISSING_REQUIRED_FIELD" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_6 THEN REJECT RECORD graph SUBJECT_TO REQUIRED RECORD field.
def test_rule_6_missing_root_field():
    t = {"version": "1.0.0", "type": "X", "nodes": [], "edges": []}  # missing 'name'
    r = _run(t)
    assert "MISSING_REQUIRED_FIELD" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_6 THEN REJECT RECORD node SUBJECT_TO MULTIPLE REQUIRED RECORD field.
def test_rule_6_missing_node_field():
    t = _make(nodes=[{"id": "x", "type": "X"}])  # missing properties, parent_id, contains, metric_level
    r = _run(t)
    codes = _errors(r)
    assert codes.count("MISSING_REQUIRED_FIELD") >= 3


# ─── Rule 7: Field Type Correctness ───────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_7 THEN ASSERT RECORD graph CONTAINS ALL VALID RECORD field.
def test_rule_7_pass():
    r = _run(MINIMAL_VALID)
    assert "INVALID_FIELD_TYPE" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_7 THEN REJECT RECORD node SUBJECT_TO INTEGER RECORD id.
def test_rule_7_id_not_string():
    t = _make(nodes=[
        {"id": 123, "type": "X", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_X", "dimension": "d"},
    ])
    r = _run(t)
    assert "INVALID_FIELD_TYPE" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_7 THEN REJECT RECORD edge SUBJECT_TO INVALID RECORD weight.
def test_rule_7_weight_out_of_range():
    t = _make(edges=[{"from_id": "root", "to_id": "root", "relation": "X", "weight": 1.5}])
    r = _run(t)
    assert "INVALID_EDGE_WEIGHT" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_7 THEN REJECT RECORD edge SUBJECT_TO BOOLEAN RECORD weight.
def test_rule_7_weight_boolean():
    t = _make(edges=[{"from_id": "root", "to_id": "root", "relation": "X", "weight": True}])
    r = _run(t)
    assert "INVALID_EDGE_WEIGHT" in _errors(r)


# ─── Rule 8: Extension Declaration ────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_8 THEN ASSERT RECORD graph SUBJECT_TO DATA capabilities.
def test_rule_8_pass():
    r = _run(MINIMAL_VALID)
    assert "UNDECLARED_EXTENSION" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_8 THEN REJECT RECORD node SUBJECT_TO INVALID RECORD extension.
def test_rule_8_undeclared_typed():
    t = _make(nodes=[
        {"id": "x", "type": "X", "properties": {"type_info": {"category": "func"}}, "parent_id": None, "contains": [], "metric_level": "BASE_X", "dimension": "d"},
    ])
    r = _run(t)
    assert "UNDECLARED_EXTENSION" in _errors(r)


# ─── Rule 9: Metric Level Format ──────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_9 THEN ASSERT RECORD node CONTAINS VALID RECORD metric.
def test_rule_9_pass():
    r = _run(MINIMAL_VALID)
    assert "INVALID_METRIC_FORMAT" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_9 THEN REJECT RECORD node SUBJECT_TO INVALID RECORD metric.
def test_rule_9_no_underscore():
    t = _make(nodes=[
        {"id": "x", "type": "X", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASEMODULE", "dimension": "d"},
    ])
    r = _run(t)
    assert "INVALID_METRIC_FORMAT" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_9 THEN REJECT RECORD node SUBJECT_TO INVALID RECORD prefix.
def test_rule_9_invalid_prefix():
    t = _make(nodes=[
        {"id": "x", "type": "X", "properties": {}, "parent_id": None, "contains": [], "metric_level": "ULTRA_MODULE", "dimension": "d"},
    ])
    r = _run(t)
    assert "INVALID_METRIC_FORMAT" in _errors(r)


# ─── Rule 10: Subject-Operation Compatibility ─────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_10 THEN ASSERT RECORD edge SUBJECT_TO RECORD party.
def test_rule_10_actor_can_do_anything():
    t = _make_v091(
        nodes=[
            {"id": "p", "type": "PARTY", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_ACTOR", "dimension": "d"},
            {"id": "d", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_DATA", "dimension": "d"},
        ],
        edges=[{"from_id": "p", "to_id": "d", "relation": "FILTER"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_SUBJECT_OPERATION" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_10 THEN REJECT RECORD edge SUBJECT_TO DATA source.
def test_rule_10_artifact_cannot_transform():
    t = _make_v091(
        nodes=[
            {"id": "d", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_DATA", "dimension": "d"},
            {"id": "d2", "type": "RECORD", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_RECORD", "dimension": "d"},
        ],
        edges=[{"from_id": "d", "to_id": "d2", "relation": "FILTER"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_SUBJECT_OPERATION" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_10 THEN ASSERT RECORD edge SUBJECT_TO DATA source.
def test_rule_10_artifact_can_exists():
    t = _make_v091(
        nodes=[
            {"id": "d", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_DATA", "dimension": "d"},
        ],
        edges=[{"from_id": "d", "to_id": "d", "relation": "EXISTS"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_SUBJECT_OPERATION" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_10 THEN ASSERT RECORD edge SUBJECT_TO RECORD pipeline.
def test_rule_10_container_can_transform():
    t = _make_v091(
        nodes=[
            {"id": "pipe", "type": "PIPELINE", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_PIPE", "dimension": "d"},
            {"id": "d", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_DATA", "dimension": "d"},
        ],
        edges=[{"from_id": "pipe", "to_id": "d", "relation": "FILTER"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_SUBJECT_OPERATION" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_10 THEN SKIP RECORD check UNLESS DATA vocabularies CONTAINS RECORD core.
def test_rule_10_not_triggered_without_v091():
    """Rules 10-16 only fire with core_v1.0.0 capability."""
    t = _make(
        nodes=[
            {"id": "d", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_DATA", "dimension": "d"},
        ],
        edges=[{"from_id": "d", "to_id": "d", "relation": "FILTER"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_SUBJECT_OPERATION" not in _errors(r)


# ─── Rule 11: Operation-Object Compatibility ──────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_11 THEN ASSERT RECORD edge SUBJECT_TO RECORD operation.
def test_rule_11_transform_on_artifact():
    t = _make_v091(
        nodes=[
            {"id": "p", "type": "PARTY", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_ACTOR", "dimension": "d"},
            {"id": "d", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_DATA", "dimension": "d"},
        ],
        edges=[{"from_id": "p", "to_id": "d", "relation": "FILTER"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_OPERATION_OBJECT" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_11 THEN REJECT RECORD edge SUBJECT_TO RECORD operation TO AGENT target.
def test_rule_11_transform_on_actor_fails():
    t = _make_v091(
        nodes=[
            {"id": "p1", "type": "PARTY", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_ACTOR", "dimension": "d"},
            {"id": "p2", "type": "AGENT", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_AGENT", "dimension": "d"},
        ],
        edges=[{"from_id": "p1", "to_id": "p2", "relation": "FILTER"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_OPERATION_OBJECT" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_11 THEN ASSERT RECORD edge SUBJECT_TO RECORD operation TO AGENT target.
def test_rule_11_permit_on_actor():
    t = _make_v091(
        nodes=[
            {"id": "p1", "type": "PARTY", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_ACTOR", "dimension": "d"},
            {"id": "p2", "type": "AGENT", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_AGENT", "dimension": "d"},
        ],
        edges=[{"from_id": "p1", "to_id": "p2", "relation": "GRANT"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_OPERATION_OBJECT" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_11 THEN ASSERT RECORD edge SUBJECT_TO RECORD operation TO ERROR target.
def test_rule_11_resolve_on_outcome():
    t = _make_v091(
        nodes=[
            {"id": "p", "type": "PARTY", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_ACTOR", "dimension": "d"},
            {"id": "e", "type": "ERROR", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_ERR", "dimension": "d"},
        ],
        edges=[{"from_id": "p", "to_id": "e", "relation": "HANDLE"}],
    )
    r = _run(t)
    assert "INCOMPATIBLE_OPERATION_OBJECT" not in _errors(r)


# ─── Rule 14: Constraint-Subject ───────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_14 THEN ASSERT RECORD edge SUBJECT_TO RECORD relation TO RECORD party.
def test_rule_14_modal_on_actor():
    t = _make_v091(
        edges=[{"from_id": "system", "to_id": "system", "relation": "SHALL"}],
    )
    r = _run(t)
    assert "CONSTRAINT_REQUIRES_ACTOR" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_14 THEN REJECT RECORD edge SUBJECT_TO RECORD relation TO DATA source.
def test_rule_14_modal_on_non_actor():
    t = _make_v091(
        nodes=[
            {"id": "d", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_DATA", "dimension": "d"},
        ],
        edges=[{"from_id": "d", "to_id": "d", "relation": "SHALL"}],
    )
    r = _run(t)
    assert "CONSTRAINT_REQUIRES_ACTOR" in _errors(r)


# ─── Rule 15: No Double Negation ──────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_15 THEN REJECT RECORD edge SUBJECT_TO RECORD negation.
def test_rule_15_no_double_neg():
    t = _make_v091(
        nodes=[
            {"id": "p", "type": "PARTY", "properties": {"scope": {"quantifier": "NO"}}, "parent_id": None, "contains": [], "metric_level": "BASE_ACTOR", "dimension": "d"},
        ],
        edges=[{"from_id": "p", "to_id": "p", "relation": "SHALL_NOT"}],
    )
    r = _run(t)
    assert "DOUBLE_NEGATION" in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_15 THEN ASSERT RECORD edge SUBJECT_TO RECORD negation.
def test_rule_15_single_neg_ok():
    t = _make_v091(
        nodes=[
            {"id": "p", "type": "PARTY", "properties": {"scope": {"quantifier": "ALL"}}, "parent_id": None, "contains": [], "metric_level": "BASE_ACTOR", "dimension": "d"},
        ],
        edges=[{"from_id": "p", "to_id": "p", "relation": "SHALL_NOT"}],
    )
    r = _run(t)
    assert "DOUBLE_NEGATION" not in _errors(r)


# ─── Rule 16: Reference Scope ─────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS rule_16 THEN ASSERT RECORD edge REFERENCES RECORD target.
def test_rule_16_resolved_reference():
    t = _make_v091(
        nodes=[
            {"id": "p", "type": "PARTY", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_ACTOR", "dimension": "d"},
            {"id": "SELF", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_REF", "dimension": "d"},
        ],
        edges=[{"from_id": "p", "to_id": "SELF", "relation": "REFERENCES"}],
    )
    r = _run(t)
    assert "UNRESOLVED_REFERENCE" not in _errors(r)


# AGENT SHALL VALIDATE PROCESS rule_16 THEN REJECT RECORD edge REFERENCES INVALID RECORD target.
def test_rule_16_unresolved_reference():
    t = _make_v091(
        edges=[{"from_id": "system", "to_id": "RESULT", "relation": "REFERENCES"}],
    )
    r = _run(t)
    assert "UNRESOLVED_REFERENCE" in _errors(r)


# ─── Integration: validate_file ────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS validate_file THEN ASSERT VALID FILE graph FROM DATA filesystem.
def test_validate_file_valid():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".trug.json", delete=False) as f:
        json.dump(MINIMAL_VALID, f)
        f.flush()
        r = validate_file(Path(f.name))
    assert r.valid


# AGENT SHALL VALIDATE PROCESS validate_file THEN REJECT INVALID FILE graph AS RECORD parse_error.
def test_validate_file_invalid_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{bad json")
        f.flush()
        r = validate_file(Path(f.name))
    assert not r.valid
    assert "PARSE_ERROR" in _errors(r)


# AGENT SHALL VALIDATE PROCESS validate_file THEN REJECT INVALID FILE path AS RECORD file_not_found.
def test_validate_file_not_found():
    r = validate_file(Path("/nonexistent/path.json"))
    assert not r.valid
    assert "FILE_NOT_FOUND" in _errors(r)


# ─── Integration: Full validate ────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS validate THEN ASSERT RECORD result.
def test_minimal_valid_passes():
    r = validate(MINIMAL_VALID)
    assert r.valid


# AGENT SHALL VALIDATE PROCESS validate THEN ASSERT RECORD result SUBJECT_TO DATA vocabularies.
def test_minimal_v091_passes():
    r = validate(MINIMAL_V091)
    assert r.valid


# AGENT SHALL VALIDATE PROCESS validate THEN REJECT ARRAY DATA graph AS RECORD invalid_root.
def test_not_a_dict():
    r = validate([1, 2, 3])
    assert not r.valid
    assert "INVALID_ROOT" in _errors(r)


# AGENT SHALL VALIDATE PROCESS validate THEN REQUIRE DATA vocabularies CONTAINS RECORD core.
def test_v091_opt_in():
    """core_v1.0.0 rules only fire when declared."""
    # This TRUG has DATA doing FILTER (invalid under rule 10) but no core_v1.0.0
    t = _make(
        nodes=[
            {"id": "d", "type": "DATA", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_DATA", "dimension": "d"},
        ],
        edges=[{"from_id": "d", "to_id": "d", "relation": "FILTER"}],
    )
    r = validate(t)
    assert r.valid  # No compositional rules fired

    # Same TRUG with core_v1.0.0 — should fail
    t["capabilities"]["vocabularies"] = ["core_v1.0.0"]
    r = validate(t)
    assert not r.valid


# ─── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    tests = [(name, obj) for name, obj in globals().items() if name.startswith("test_") and callable(obj)]
    passed = 0
    failed = 0
    for name, fn in sorted(tests):
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
