"""Tests for trugs-compliance-check.

# AGENT claude SHALL VALIDATE PROCESS compliance_check SUBJECT_TO DATA standard_dark_code_compliance.

Covers C1, C3, C4, C5, C7 behavior end-to-end against synthetic fixtures
written to a temp directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from trugs_tools import compliance_check as cc


# =============================================================================
# HELPERS
# =============================================================================


# AGENT claude SHALL DEFINE A RECORD fixture.
@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    return tmp_path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# =============================================================================
# C1 — function-level TRUG/L comment on public def
# =============================================================================


# AGENT SHALL VALIDATE PROCESS c1 THEN ASSERT RECORD compliant_function IMPLEMENTS DATA trl.
def test_c1_compliant_function_passes(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
# AGENT claude SHALL VALIDATE DATA input.
def public_function(x):
    return x
""")
    report = cc.audit(tmp_repo)
    c1 = [v for v in report.violations if v.rule == "C1"]
    assert c1 == [], f"unexpected C1 violations: {c1}"
    assert report.functions_checked == 1


# AGENT SHALL VALIDATE PROCESS c1 THEN ASSERT RECORD missing_comment FEEDS RECORD violation.
def test_c1_missing_comment_flagged(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
def public_function(x):
    return x
""")
    report = cc.audit(tmp_repo)
    c1 = [v for v in report.violations if v.rule == "C1"]
    assert len(c1) == 1
    assert "has no TRUG/L comment" in c1[0].message
    assert c1[0].symbol == "public_function"


# AGENT SHALL VALIDATE PROCESS c1 THEN REJECT DATA unparseable_comment.
def test_c1_unparseable_comment_flagged(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
# this is just plain English, not TRUG/L
def public_function(x):
    return x
""")
    report = cc.audit(tmp_repo)
    c1 = [v for v in report.violations if v.rule == "C1"]
    assert len(c1) == 1
    assert "does not parse as TRUG/L" in c1[0].message


# AGENT SHALL VALIDATE PROCESS c1 THEN FILTER PRIVATE FUNCTION FROM DATA audit.
def test_c1_private_function_exempt(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
def _private_function(x):
    return x
""")
    report = cc.audit(tmp_repo)
    assert report.violation_count == 0
    assert report.functions_checked == 0


# AGENT SHALL VALIDATE PROCESS c1 THEN FILTER FUNCTION dunder FROM DATA audit.
def test_c1_dunder_exempt(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
# AGENT claude SHALL DEFINE RECORD thing.
class Thing:
    def __repr__(self):
        return "thing"
""")
    report = cc.audit(tmp_repo)
    c1 = [v for v in report.violations if v.rule == "C1"]
    assert c1 == [], f"unexpected C1 violations: {c1}"


# AGENT SHALL VALIDATE PROCESS c1 THEN FILTER FUNCTION nested FROM DATA audit.
def test_c1_nested_function_exempt(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
# AGENT claude SHALL VALIDATE DATA outer.
def outer():
    def inner():
        return 1
    return inner
""")
    report = cc.audit(tmp_repo)
    c1 = [v for v in report.violations if v.rule == "C1"]
    assert c1 == [], f"nested inner should be exempt: {c1}"


# AGENT SHALL VALIDATE PROCESS c1 THEN FILTER DATA banner FROM DATA comment_block.
def test_c1_banner_comment_doesnt_become_trl(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
# ===============================================================
# SECTION HEADING
# ===============================================================

# AGENT claude SHALL VALIDATE DATA input.
def public_function(x):
    return x
""")
    report = cc.audit(tmp_repo)
    c1 = [v for v in report.violations if v.rule == "C1"]
    assert c1 == [], f"banner should be ignored: {c1}"


# =============================================================================
# C3 — TRUG node trl property parses
# =============================================================================


# AGENT SHALL VALIDATE PROCESS c3 THEN ASSERT RECORD node IMPLEMENTS VALID DATA trl.
def test_c3_compliant_node_passes(tmp_repo: Path) -> None:
    _write(tmp_repo / "folder.trug.json", json.dumps({
        "nodes": [{
            "id": "fn",
            "type": "FUNCTION",
            "properties": {
                "trl": "AGENT claude SHALL VALIDATE DATA input.",
                "name": "fn",
            },
            "parent_id": None,
            "contains": [],
            "metric_level": "BASE_FUNCTION",
            "dimension": "d",
        }],
        "edges": [],
    }))
    report = cc.audit(tmp_repo)
    c3 = [v for v in report.violations if v.rule == "C3"]
    assert c3 == []
    assert report.nodes_checked == 1


# AGENT SHALL VALIDATE PROCESS c3 THEN REJECT INVALID DATA trl FROM RECORD node.
def test_c3_invalid_trl_flagged(tmp_repo: Path) -> None:
    _write(tmp_repo / "folder.trug.json", json.dumps({
        "nodes": [{
            "id": "fn",
            "type": "FUNCTION",
            "properties": {
                "trl": "FORMAT X AS WHATEVER nonsense.",
                "name": "fn",
            },
            "parent_id": None,
            "contains": [],
            "metric_level": "BASE_FUNCTION",
            "dimension": "d",
        }],
        "edges": [],
    }))
    report = cc.audit(tmp_repo)
    c3 = [v for v in report.violations if v.rule == "C3"]
    assert len(c3) == 1
    assert "does not parse" in c3[0].message


# =============================================================================
# C4 — test function has AGENT SHALL VALIDATE comment
# =============================================================================


# AGENT SHALL VALIDATE PROCESS c4 THEN ASSERT FUNCTION test IMPLEMENTS DATA trl_comment.
def test_c4_compliant_test_passes(tmp_repo: Path) -> None:
    _write(tmp_repo / "test_thing.py", """
# AGENT SHALL VALIDATE DATA input.
def test_something():
    assert True
""")
    report = cc.audit(tmp_repo)
    c4 = [v for v in report.violations if v.rule == "C4"]
    assert c4 == []
    assert report.tests_checked == 1


# AGENT SHALL VALIDATE PROCESS c4 THEN ASSERT FUNCTION test FEEDS RECORD violation.
def test_c4_missing_test_comment_flagged(tmp_repo: Path) -> None:
    _write(tmp_repo / "test_thing.py", """
def test_something():
    assert True
""")
    report = cc.audit(tmp_repo)
    c4 = [v for v in report.violations if v.rule == "C4"]
    assert len(c4) == 1
    assert "has no TRUG/L comment" in c4[0].message


# AGENT SHALL VALIDATE PROCESS c4 THEN REJECT DATA wrong_prefix FROM FUNCTION test.
def test_c4_wrong_prefix_flagged(tmp_repo: Path) -> None:
    _write(tmp_repo / "test_thing.py", """
# AGENT claude SHALL READ DATA input.
def test_something():
    assert True
""")
    report = cc.audit(tmp_repo)
    c4 = [v for v in report.violations if v.rule == "C4"]
    assert len(c4) == 1
    assert "AGENT SHALL VALIDATE" in c4[0].message


# AGENT SHALL VALIDATE DATA c4.
def test_c4_helper_in_test_class_exempt(tmp_repo: Path) -> None:
    """helper_setup and setUp in a Test* class are NOT test functions — no C4."""
    _write(tmp_repo / "test_thing.py", """
class TestExample:
    # AGENT SHALL VALIDATE DATA input.
    def test_foo(self):
        assert True

    def helper_setup(self):
        return 42

    def setUp(self):
        self.x = 1
""")
    report = cc.audit(tmp_repo)
    c4 = [v for v in report.violations if v.rule == "C4"]
    assert c4 == [], f"helper/setUp should not trigger C4: {c4}"
    # Only test_foo should count as a test
    assert report.tests_checked == 1


# =============================================================================
# C5 — TEST node has outbound VALIDATES edge
# =============================================================================


# AGENT SHALL VALIDATE PROCESS c5 THEN ASSERT RECORD test_node FEEDS RECORD function.
def test_c5_test_with_validates_edge_passes(tmp_repo: Path) -> None:
    _write(tmp_repo / "folder.trug.json", json.dumps({
        "nodes": [
            {"id": "test_x", "type": "TEST", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_TEST", "dimension": "d"},
            {"id": "fn", "type": "FUNCTION", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_FUNCTION", "dimension": "d"},
        ],
        "edges": [
            {"from_id": "test_x", "to_id": "fn", "relation": "VALIDATES"},
        ],
    }))
    report = cc.audit(tmp_repo)
    c5 = [v for v in report.violations if v.rule == "C5"]
    assert c5 == []


# AGENT SHALL VALIDATE PROCESS c5 THEN ASSERT RECORD orphan_test FEEDS RECORD violation.
def test_c5_orphan_test_flagged(tmp_repo: Path) -> None:
    _write(tmp_repo / "folder.trug.json", json.dumps({
        "nodes": [
            {"id": "test_orphan", "type": "TEST", "properties": {}, "parent_id": None, "contains": [], "metric_level": "BASE_TEST", "dimension": "d"},
        ],
        "edges": [],
    }))
    report = cc.audit(tmp_repo)
    c5 = [v for v in report.violations if v.rule == "C5"]
    assert len(c5) == 1
    assert "no outbound VALIDATES edge" in c5[0].message


# =============================================================================
# EXCLUSIONS
# =============================================================================


# AGENT SHALL VALIDATE PROCESS discovery THEN FILTER DATA zzz_archive FROM DATA audit.
def test_zzz_excluded(tmp_repo: Path) -> None:
    _write(tmp_repo / "zzz_archive/old.py", """
def bad_function():
    return 1
""")
    report = cc.audit(tmp_repo)
    assert report.files_checked == 0
    assert report.violation_count == 0


# AGENT SHALL VALIDATE PROCESS discovery THEN FILTER DATA pycache FROM DATA audit.
def test_pycache_excluded(tmp_repo: Path) -> None:
    _write(tmp_repo / "__pycache__/compiled.py", """
def bad_function():
    return 1
""")
    report = cc.audit(tmp_repo)
    assert report.files_checked == 0


# =============================================================================
# REPORT METRICS
# =============================================================================


# AGENT SHALL VALIDATE PROCESS metric THEN AGGREGATE RECORD violation TO DATA compliance_percent.
def test_compliance_percent_for_all_violations(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
def a():
    return 1

def b():
    return 2
""")
    report = cc.audit(tmp_repo)
    # Both a and b trigger C1. Each function counts as C1+C4 opportunities (2 each).
    # 2 functions * 2 opportunities = 4, violations = 2, passed = 2, compliance = 50%.
    assert report.compliance_percent == 50.0


# AGENT SHALL VALIDATE PROCESS metric THEN ASSERT DATA compliance_percent FROM RECORD empty_report.
def test_compliance_percent_hundred_when_empty(tmp_repo: Path) -> None:
    report = cc.audit(tmp_repo)
    assert report.compliance_percent == 100.0
    assert report.violation_count == 0


# AGENT SHALL VALIDATE PROCESS metric THEN GROUP RECORD violation BY DATA rule.
def test_violations_by_rule(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", """
def a():
    return 1

def b():
    return 2
""")
    _write(tmp_repo / "test_thing.py", """
def test_c():
    assert True
""")
    report = cc.audit(tmp_repo)
    grouped = report.violations_by_rule
    assert grouped.get("C1") == 2
    assert grouped.get("C4") == 1


# =============================================================================
# CLI
# =============================================================================


# AGENT SHALL VALIDATE PROCESS main THEN ASSERT DATA exit_code FROM RECORD clean_report.
def test_main_returns_zero_for_clean(tmp_repo: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = cc.main([str(tmp_repo)])
    assert exit_code == 0


# AGENT SHALL VALIDATE PROCESS main THEN ASSERT DATA strict_exit FROM RECORD violation.
def test_main_strict_returns_one_on_violation(tmp_repo: Path, capsys: pytest.CaptureFixture) -> None:
    _write(tmp_repo / "src.py", "def a():\n    return 1\n")
    exit_code = cc.main([str(tmp_repo), "--strict"])
    assert exit_code == 1


# AGENT SHALL VALIDATE PROCESS main THEN WRITE DATA json_output FROM RECORD report.
def test_main_json_output(tmp_repo: Path, capsys: pytest.CaptureFixture) -> None:
    _write(tmp_repo / "src.py", "def a():\n    return 1\n")
    cc.main([str(tmp_repo), "--json"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "compliance_percent" in parsed
    assert "violations" in parsed
    assert parsed["violation_count"] == 1


# AGENT SHALL VALIDATE PROCESS main THEN WRITE DATA baseline TO FILE compliance_baseline.
def test_main_baseline_update_writes_file(tmp_repo: Path) -> None:
    _write(tmp_repo / "src.py", "def a():\n    return 1\n")
    cc.main([str(tmp_repo), "--baseline-update"])
    baseline_path = tmp_repo / ".github" / "compliance-baseline.json"
    assert baseline_path.exists()
    data = json.loads(baseline_path.read_text())
    assert "compliance_percent" in data
