# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json

from trugs_tools.compliance_check import (
    Report,
    audit,
    check_invariants_across_repo,
    check_trug_file,
    main,
    render_text,
)


def _graph(nodes, edges=()):
    return {
        "name": "checks",
        "version": "1.0.0",
        "type": "PROJECT",
        "dimension": "system",
        "dimensions": {"system": {"description": "Compliance checks"}},
        "nodes": [
            {
                "id": name,
                "type": kind,
                "properties": props,
                "parent_id": None,
                "contains": [],
                "metric_level": "BASE_" + kind,
                "dimension": "system",
            }
            for name, kind, props in nodes
        ],
        "edges": [
            {"from_id": source, "to_id": target, "relation": relation}
            for source, target, relation in edges
        ],
    }


def _write_graph(path, nodes, edges=()):
    path.write_text(json.dumps(_graph(nodes, edges)), encoding="utf-8")


# AGENT SHALL VALIDATE RECORD invariant_coverage.
def test_c6_requires_real_assertion_and_test(tmp_path):
    graph = tmp_path / "folder.trug.json"
    source = tmp_path / "module.py"
    _write_graph(graph, [("ledger", "RECORD", {"invariant_probe": True})])
    test = (
        "# AGENT SHALL VALIDATE RECORD invariant_probe.\n"
        "def test_probe():\n    assert True\n"
    )
    cases = [
        ("# assert invariant_probe\n# AGENT SHALL VALIDATE invariant_probe\n", 2),
        ('text = "assert invariant_probe"\n', 2),
        ("assert True  # invariant_probe\n\n" + test, 0),
        ("# invariant_probe\nassert True\n\n" + test, 0),
        ("assert (\n    True  # invariant_probe\n)\n\n" + test, 0),
        ("assert True, 'invariant_probe'\n\n" + test, 0),
        ("assert True  # invariant_probe_extra\n\n" + test, 1),
        ("assert True  # prefix_invariant_probe\n\n" + test, 1),
        ("# invariant_probe\n\nassert True\n\n" + test, 1),
        (test.replace("assert True", "assert True  # invariant_probe"), 1),
        (test.replace("    assert True", "    def inner():\n        assert True  # invariant_probe"), 1),
        ("class TestProbe:\n    # invariant_probe\n    def testProbe(self):\n        assert True  # invariant_probe\n", 1),
        ("assert True  # invariant_probe\n\n# invariant_probe\ndef helper():\n    pass\n", 1),
        ("assert True  # invariant_probe\n\n" + test.replace("invariant_probe", "invariant_probe_extra"), 1),
        ("assert True  # invariant_probe\n\nclass TestProbe:\n    # invariant_probe\n    async def testProbe(self):\n        pass\n", 0),
    ]
    for text, missing in cases:
        source.write_text(text, encoding="utf-8")
        report = Report()
        check_invariants_across_repo(tmp_path, report, [source], [graph])
        assert report.violation_count == missing, text
        assert all(v.rule == "C6" and v.symbol == "ledger" for v in report.violations)
        assert all(v.message in {
            "invariant 'invariant_probe' on node 'ledger' has no matching assertion in code",
            "invariant 'invariant_probe' on node 'ledger' has no matching test",
        } for v in report.violations)


# AGENT SHALL VALIDATE RECORD declaration_coverage.
def test_c2_requires_graph_node_for_public_declarations(tmp_path):
    source = tmp_path / "module.py"
    graph = tmp_path / "folder.trug.json"
    source.write_text(
        "# AGENT worker SHALL READ FILE input.\ndef public_function():\n    return 1\n",
        encoding="utf-8",
    )
    _write_graph(graph, [("ledger", "RECORD", {})])
    report = audit(tmp_path)
    missing = [v for v in report.violations if v.rule == "C2"]
    assert [(v.path, v.line, v.symbol) for v in missing] == [(source, 2, "public_function")]
    for kind in ("FUNCTION", "PROCESS", "CLASS", "METHOD", "STAGE"):
        _write_graph(graph, [("entry", kind, {"name": "public_function"})])
        assert not [v for v in audit(tmp_path).violations if v.rule == "C2"]
    source.write_text("class Box:\n    async def open(self):\n        pass\n", encoding="utf-8")
    for kind, expected in (("CLASS", []), ("FUNCTION", ["open"])):
        _write_graph(graph, [("Box", kind, {})])
        assert [v.symbol for v in audit(tmp_path).violations if v.rule == "C2"] == expected
    graph.write_text("{broken", encoding="utf-8")
    assert [v.symbol for v in audit(tmp_path).violations if v.rule == "C2"] == ["Box", "open"]
    _write_graph(graph, [("Box", "CLASS", {})])
    child = tmp_path / "pkg"
    child.mkdir()
    nested = child / "module.py"
    nested.write_text("class Box:\n    pass\n", encoding="utf-8")
    assert [(v.path, v.symbol) for v in audit(tmp_path).violations if v.rule == "C2"] == [(nested, "Box")]


# AGENT SHALL VALIDATE RECORD test_target_types.
def test_c5_requires_present_supported_target(tmp_path):
    graph = tmp_path / "folder.trug.json"
    for kind in ("RECORD", "DOCUMENT", "FUNCTION", "PROCESS", "CLASS", "METHOD", "STAGE", "SPECIFICATION"):
        _write_graph(graph, [("check", "TEST", {}), ("target", kind, {})], [("check", "target", "validates")])
        report = Report()
        check_trug_file(graph, report, tmp_path)
        assert [v.symbol for v in report.violations if v.rule == "C5"] == (
            ["check"] if kind in ("RECORD", "DOCUMENT") else []
        )
    _write_graph(graph, [("check", "TEST", {})], [("check", "missing", "VALIDATES")])
    report = Report()
    check_trug_file(graph, report, tmp_path)
    assert [v.symbol for v in report.violations if v.rule == "C5"] == ["check"]
    _write_graph(graph, [("check", "TEST", {}), ("target", "SPECIFICATION", {})],
                 [("check", "missing", "VALIDATES"), ("check", "target", "VALIDATES")])
    report = Report()
    check_trug_file(graph, report, tmp_path)
    assert not [v for v in report.violations if v.rule == "C5"]


# AGENT SHALL VALIDATE RECORD check_opportunities.
def test_score_counts_each_rule_opportunity(tmp_path):
    graph = tmp_path / "folder.trug.json"
    _write_graph(graph, [("pass_test", "TEST", {}), ("fail_test", "TEST", {}), ("target", "FUNCTION", {})],
                 [("pass_test", "target", "VALIDATES")])
    report = audit(tmp_path)
    assert report.compliance_percent == 50.0
    expected = {"C1": 0, "C2": 1, "C3": 0, "C4": 0, "C5": 2, "C6": 0, "C7": 1}
    assert report.to_dict()["opportunities"] == expected
    assert (report.files_checked, report.functions_checked, report.tests_checked,
            report.nodes_checked, report.trug_files_checked) == (1, 0, 0, 0, 1)
    text = render_text(report, tmp_path)
    for rule, count in expected.items():
        assert f"{rule}: {count}" in text
    assert Report().compliance_percent == 100.0
    source = tmp_path / "module.py"
    source.write_text(
        "# AGENT worker SHALL READ FILE input.\ndef target():\n"
        "    assert True  # invariant_probe\n\n"
        "# AGENT SHALL VALIDATE RECORD invariant_probe.\ndef test_target():\n    assert True\n",
        encoding="utf-8",
    )
    _write_graph(graph, [("target", "FUNCTION", {"invariant_probe": True, "trl": "AGENT worker SHALL READ FILE input."})])
    report = audit(tmp_path)
    expected = {"C1": 1, "C2": 2, "C3": 1, "C4": 1, "C5": 0, "C6": 2, "C7": 1}
    assert report.to_dict()["opportunities"] == expected
    assert report.compliance_percent == 100.0


# AGENT SHALL VALIDATE RECORD baseline_errors.
def test_default_rejects_unreadable_baseline(tmp_path, capsys):
    baseline = tmp_path / ".github" / "compliance-baseline.json"
    baseline.parent.mkdir()
    invalid = ["[]", "not JSON", "null", "{}", '{"compliance_percent": true}',
               '{"compliance_percent": false}', '{"compliance_percent": "100"}',
               '{"compliance_percent": null}', '{"compliance_percent": []}']
    for text in invalid:
        baseline.write_text(text, encoding="utf-8")
        assert main([str(tmp_path)]) == 2, text
        assert str(baseline) in capsys.readouterr().err
        assert main(["--strict", str(tmp_path)]) == 0
        capsys.readouterr()
    baseline.write_bytes(b"\xff")
    assert main([str(tmp_path)]) == 2
    assert str(baseline) in capsys.readouterr().err
    baseline.unlink()
    baseline.mkdir()
    assert main([str(tmp_path)]) == 2
    assert str(baseline) in capsys.readouterr().err
    baseline.rmdir()
    for percent in (100, 100.0):
        baseline.write_text(json.dumps({"compliance_percent": percent}), encoding="utf-8")
        assert main([str(tmp_path)]) == 0
        capsys.readouterr()
    baseline.write_text("not JSON", encoding="utf-8")
    assert main(["--baseline-update", str(tmp_path)]) == 0
    assert json.loads(baseline.read_text(encoding="utf-8"))["compliance_percent"] == 100.0
    capsys.readouterr()
    baseline.unlink()
    assert main([str(tmp_path)]) == 0
