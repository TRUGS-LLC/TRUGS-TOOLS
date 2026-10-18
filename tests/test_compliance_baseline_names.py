# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json
import os

import pytest

from trugs_tools.compliance_check import audit, main
from trugs_tools.validate import validate_file


# AGENT SHALL VALIDATE RECORD stage_names.
def test_c2_handles_nonstring_stage_names(tmp_path, capsys):
    for index, value in enumerate((["pipeline"], {"a": "pipeline"}, 42, True, None, [], {})):
        root = tmp_path / str(index)
        root.mkdir()
        graph = root / "graph.trug.json"
        graph.write_text(json.dumps({
            "name": "checks", "version": "1.0.0", "type": "PROJECT",
            "dimension": "system", "dimensions": {"system": {"description": "Checks"}},
            "nodes": [{"id": "stage", "type": "STAGE", "properties": {"name": value},
                       "parent_id": None, "contains": [], "metric_level": "BASE_STAGE",
                       "dimension": "system"}],
            "edges": [],
        }), encoding="utf-8")
        assert validate_file(graph).valid
        assert main(["--strict", "--json", str(root)]) == 0
        output = capsys.readouterr()
        report = json.loads(output.out)
        assert report["violations"] == []
        assert report["files_checked"] == 1
        assert report["compliance_percent"] == 100.0
        assert output.err == ""
        source = root / "module.py"
        source.write_text(
            "# AGENT worker SHALL READ FILE input.\ndef task():\n    pass\n", encoding="utf-8"
        )
        report = audit(root)
        assert [(v.rule, v.path, v.line, v.symbol) for v in report.violations] == [
            ("C2", source, 2, "task")
        ]


# AGENT SHALL VALIDATE RECORD baseline_access.
def test_default_rejects_unsearchable_baseline_parent(tmp_path, capsys):
    if os.geteuid() == 0:
        pytest.skip("root can search mode-0 folders; permission denial needs a non-root process")
    baseline = tmp_path / ".github" / "compliance-baseline.json"
    assert main([str(tmp_path)]) == 0
    capsys.readouterr()
    baseline.parent.mkdir()
    assert main([str(tmp_path)]) == 0
    capsys.readouterr()
    baseline.write_text("not JSON", encoding="utf-8")
    mode = baseline.parent.stat().st_mode
    baseline.parent.chmod(0)
    try:
        assert main([str(tmp_path)]) == 2
        assert str(baseline) in capsys.readouterr().err
        assert main(["--strict", str(tmp_path)]) == 0
        assert capsys.readouterr().err == ""
    finally:
        baseline.parent.chmod(mode)
    assert baseline.read_text(encoding="utf-8") == "not JSON"
    baseline.chmod(0)
    try:
        assert main([str(tmp_path)]) == 2
        assert str(baseline) in capsys.readouterr().err
    finally:
        baseline.chmod(0o600)
    assert main(["--baseline-update", str(tmp_path)]) == 0
    assert json.loads(baseline.read_text(encoding="utf-8"))["compliance_percent"] == 100.0
    capsys.readouterr()
    baseline.unlink()
    baseline.parent.rmdir()
    baseline.parent.write_text("regular file", encoding="utf-8")
    assert main([str(tmp_path)]) == 2
    assert str(baseline) in capsys.readouterr().err
    assert main(["--strict", str(tmp_path)]) == 0
    assert capsys.readouterr().err == ""


# AGENT SHALL VALIDATE RECORD baseline_json_numbers.
def test_default_rejects_nonjson_numeric_constants(tmp_path, capsys):
    baseline = tmp_path / ".github" / "compliance-baseline.json"
    baseline.parent.mkdir()
    for constant in ("NaN", "Infinity", "-Infinity"):
        for content in ('{"compliance_percent": ' + constant + '}',
                        '{"compliance_percent": 100, "extra": ' + constant + '}'):
            baseline.write_text(content, encoding="utf-8")
            assert main([str(tmp_path)]) == 2
            assert str(baseline) in capsys.readouterr().err
            assert main(["--strict", str(tmp_path)]) == 0
            assert capsys.readouterr().err == ""
            for options in (["--baseline-update"], ["--strict", "--baseline-update"]):
                baseline.write_text(content, encoding="utf-8")
                assert main([*options, str(tmp_path)]) == 0
                assert json.loads(baseline.read_text(encoding="utf-8"))["compliance_percent"] == 100.0
                capsys.readouterr()
    for number, expected in (("100", 0), ("100.0", 0), ("-1", 0), ("101", 1),
                             ("1e400", 1), ("-1e400", 0)):
        baseline.write_text('{"compliance_percent": ' + number + '}', encoding="utf-8")
        assert main([str(tmp_path)]) == expected
        assert "cannot read baseline" not in capsys.readouterr().err
    for boolean in ("true", "false"):
        baseline.write_text('{"compliance_percent": ' + boolean + '}', encoding="utf-8")
        assert main([str(tmp_path)]) == 2
        assert str(baseline) in capsys.readouterr().err
