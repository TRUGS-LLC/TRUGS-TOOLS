# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

from trugs_tools.compliance_check import Report, audit, check_trug_file, render_text
from trugs_tools.validate import validate


# AGENT SHALL VALIDATE PROCESS stage_compliance.
def test_runtime_stage_passes_c2(tmp_path):
    graph = {
        "name": "minimal", "version": "1.0.0", "type": "PROJECT", "dimension": "control",
        "dimensions": {"control": {"description": "a runtime control surface", "base_level": "BASE"}},
        "capabilities": {"extensions": [], "vocabularies": ["core_v2.0.0"], "profiles": []},
        "nodes": [
            {"id": "run", "type": "PIPELINE", "properties": {}, "parent_id": None,
             "contains": ["halted"], "metric_level": "DEKA_PIPELINE", "dimension": "control"},
            {"id": "halted", "type": "STAGE", "properties": {}, "parent_id": "run",
             "contains": [], "metric_level": "BASE_STAGE", "dimension": "control"}],
        "edges": []}
    assert validate(graph).valid
    path = tmp_path / "surface.trug.json"
    path.write_text(json.dumps(graph))
    report = audit(tmp_path)
    assert not [v for v in report.violations if v.rule == "C2"]
    assert report.compliance_percent == 100.0
    assert "Compliance: 100.0%" in render_text(report, tmp_path)
    graph["nodes"][1].update(type="FUNCTION", metric_level="BASE_FUNCTION")
    path.write_text(json.dumps(graph))
    report = audit(tmp_path)
    assert any(v.rule == "C2" and v.symbol == "halted" for v in report.violations)

    repository = Path(__file__).resolve().parents[1]
    report = Report()
    check_trug_file(repository / "folder.trug.json", report, repository, folder_py_names=set())
    assert not [v for v in report.violations if v.rule == "C2"]
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "module.py").write_text("def ready():\n    return True\n")
    folder_graph = {
        "name": "generated", "version": "1.0.0", "type": "PROJECT", "dimension": "code",
        "dimensions": {"code": {"description": "folder code", "base_level": "BASE"}},
        "capabilities": {"extensions": [], "vocabularies": ["core_v2.0.0"], "profiles": []},
        "nodes": [
            {"id": "folder", "type": "FOLDER", "properties": {"name": "generated"},
             "parent_id": None, "contains": ["ready"], "metric_level": "DEKA_FOLDER",
             "dimension": "code"},
            {"id": "ready", "type": "FUNCTION", "properties": {"name": "ready"},
             "parent_id": "folder", "contains": [], "metric_level": "BASE_FUNCTION",
             "dimension": "code"}],
        "edges": [{"from_id": "folder", "to_id": "ready", "relation": "CONTAINS"}]}
    assert validate(folder_graph).valid
    (generated / "folder.trug.json").write_text(json.dumps(folder_graph))
    report = audit(generated)
    assert not [v for v in report.violations if v.rule == "C2"]
