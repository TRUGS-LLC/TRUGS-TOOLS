# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json

import pytest

from trugs_tools.compliance_check import Report, check_invariants_across_repo
from trugs_tools.validate import validate_file


@pytest.fixture(params=("\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"),
                ids=("vt", "ff", "fs", "gs", "rs", "nel", "ls", "ps"))
def separator(request):
    return request.param


@pytest.fixture(params=("\n", "\r\n", "\r"), ids=("lf", "crlf", "cr"))
def newline(request):
    return request.param


def _check_coverage(root, text, newline, missing):
    graph = root / "folder.trug.json"
    graph.write_text(json.dumps({
        "name": "checks", "version": "1.0.0", "type": "PROJECT",
        "dimension": "system", "dimensions": {"system": {"description": "Checks"}},
        "nodes": [{"id": "ledger", "type": "RECORD",
                   "properties": {"invariant_probe": True}, "parent_id": None,
                   "contains": [], "metric_level": "BASE_RECORD", "dimension": "system"}],
        "edges": [],
    }), encoding="utf-8")
    assert validate_file(graph).valid
    source = root / "module.py"
    # Keep the test comment before separators so its existing reader is unaffected.
    prefix = "# AGENT SHALL VALIDATE RECORD invariant_probe.\ndef test_check():\n    pass\n\n"
    source.write_bytes((prefix + text).replace("\n", newline).encode("utf-8"))
    report = Report()
    check_invariants_across_repo(root, report, [source], [graph])
    assert report.opportunities["C6"] == 2
    assert [(v.rule, v.path, v.symbol, v.message) for v in report.violations] == [
        ("C6", graph, "ledger",
         "invariant 'invariant_probe' on node 'ledger' has no matching assertion in code")
    ] * missing


# AGENT SHALL VALIDATE RECORD assertion_after_string.
def test_c6_finds_assertion_after_string_separator(tmp_path, separator, newline):
    _check_coverage(tmp_path, f'text = "a{separator}b"\nassert invariant_probe\n', newline, 0)
    _check_coverage(tmp_path, f'text = "a{separator}b"\n# invariant_probe\nassert True\n', newline, 0)
    _check_coverage(tmp_path, f'# before{separator}invariant_probe\nassert True\n', newline, 0)


# AGENT SHALL VALIDATE RECORD string_without_assertion.
def test_c6_rejects_key_only_in_string_before_assertion(tmp_path, separator, newline):
    _check_coverage(tmp_path, f'text = "a{separator}invariant_probe"\nassert True\n', newline, 1)
    _check_coverage(tmp_path, f'text = "a{separator}invariant_probe"\n# unrelated\nassert True\n', newline, 1)


# AGENT SHALL VALIDATE RECORD assertion_message_lines.
def test_c6_reads_assertion_message_with_separator(tmp_path, separator, newline):
    _check_coverage(tmp_path, f'assert True, "a{separator}b"  # invariant_probe\n', newline, 0)
    _check_coverage(tmp_path, f'assert True, "a{separator}invariant_probe"\n', newline, 0)
    _check_coverage(tmp_path, f'assert (\n    True\n), "a{separator}invariant_probe"\n', newline, 0)
    _check_coverage(tmp_path, f'assert True, "a{separator}invariant_probe_extra"\n', newline, 1)
