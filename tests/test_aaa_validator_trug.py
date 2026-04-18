"""Tests for validate_aaa_trug."""

import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trugs_tools.aaa_validator import validate_aaa, validate_aaa_trug


CANONICAL_PATH = Path(__file__).resolve().parent / "fixtures" / "aaa_canonical_example.trug.json"


def _canonical_data():
    return json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))


# AGENT SHALL VALIDATE PROCESS test_validate_aaa_trug_accepts_canonical_example.
def test_validate_aaa_trug_accepts_canonical_example():
    valid, errors = validate_aaa_trug(_canonical_data())
    assert valid
    assert errors == []


# AGENT SHALL VALIDATE PROCESS test_validate_aaa_trug_rejects_missing_node_core_fields.
def test_validate_aaa_trug_rejects_missing_node_core_fields():
    data = _canonical_data()
    data["nodes"][0].pop("dimension")
    valid, errors = validate_aaa_trug(data)
    assert not valid
    assert any("missing CORE fields" in err and "dimension" in err for err in errors)


# AGENT SHALL VALIDATE PROCESS test_validate_aaa_trug_rejects_unknown_node_type.
def test_validate_aaa_trug_rejects_unknown_node_type():
    data = _canonical_data()
    data["nodes"][1]["type"] = "UNKNOWN_TYPE"
    valid, errors = validate_aaa_trug(data)
    assert not valid
    assert any("unknown aaa_v1 node type" in err for err in errors)


# AGENT SHALL VALIDATE PROCESS test_validate_aaa_trug_rejects_dangling_edge_with_specific_message.
def test_validate_aaa_trug_rejects_dangling_edge_with_specific_message():
    data = _canonical_data()
    data["edges"][0]["to_id"] = "missing_phase"
    valid, errors = validate_aaa_trug(data)
    assert not valid
    assert any("Dangling edge" in err and "missing_phase" in err for err in errors)


# AGENT SHALL VALIDATE PROCESS test_validate_aaa_trug_rejects_one_unpaired_coding_task_with_id_and_name.
def test_validate_aaa_trug_rejects_one_unpaired_coding_task_with_id_and_name():
    data = _canonical_data()
    data["edges"] = [
        edge
        for edge in data["edges"]
        if not (edge.get("relation") == "audits" and edge.get("to_id") == "task_enforce_governance")
    ]
    valid, errors = validate_aaa_trug(data)
    assert not valid
    assert any(
        "task_enforce_governance" in err and "Add governance checks for generated TRUG output" in err
        for err in errors
    )


# AGENT SHALL VALIDATE PROCESS test_validate_aaa_trug_rejects_all_unpaired_coding_tasks.
def test_validate_aaa_trug_rejects_all_unpaired_coding_tasks():
    data = _canonical_data()
    data["edges"] = [edge for edge in data["edges"] if edge.get("relation") != "audits"]
    valid, errors = validate_aaa_trug(data)
    assert not valid
    unpaired = [err for err in errors if "Unpaired CODING task" in err]
    assert len(unpaired) == 2


# AGENT SHALL VALIDATE PROCESS test_validate_aaa_markdown_path_unchanged.
def test_validate_aaa_markdown_path_unchanged():
    content = """
## VISION
content
## FEASIBILITY
content
## SPECIFICATIONS
content
## ARCHITECTURE
**Phase Status:** COMPLETE
System design here.
## CODING
content
## TESTING
content
## DEPLOYMENT
content
"""
    path = Path("/tmp/test_aaa_validator_trug_markdown.md")
    path.write_text(content, encoding="utf-8")
    try:
        valid, errors = validate_aaa(path)
        assert valid, errors
    finally:
        path.unlink(missing_ok=True)
