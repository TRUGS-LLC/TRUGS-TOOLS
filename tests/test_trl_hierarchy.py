# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json

import pytest

from trugs_tools import trl
from trugs_tools.lang_cli import main
from trugs_tools.validate import validate


def _identity(graph):
    return (
        sorted((n["id"], n["type"]) for n in graph["nodes"]),
        sorted((e["from_id"], e["to_id"], e["relation"]) for e in graph["edges"]),
    )


@pytest.mark.parametrize("nested", [False, True], ids=["parentless", "nested"])
def test_hierarchy_changes_keep_text_and_identity(nested, tmp_path, capsys):
    graph = trl.compile("AGENT worker SHALL READ FILE input.")
    nodes = {n["id"]: n for n in graph["nodes"]}
    nodes["root"]["contains"].remove("input")
    nodes["input"]["parent_id"] = "worker" if nested else None
    if nested:
        nodes["worker"]["contains"].append("input")
    assert validate(graph).valid
    path = tmp_path / "nested.trug.json"
    path.write_text(json.dumps(graph))
    assert main(["trl", "decompile", str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "AGENT worker SHALL READ FILE input.\n"
    assert not captured.err
    restored = trl.compile(captured.out)
    assert validate(restored).valid
    assert _identity(restored) == _identity(graph)


def test_isolated_non_noun_keeps_text(tmp_path, capsys):
    graph = trl.compile("AGENT worker SHALL READ FILE input.")
    graph["nodes"].append({
        "id": "extra-folder",
        "type": "FOLDER",
        "properties": {"purpose": "Additional hierarchy"},
        "parent_id": None,
        "contains": [],
        "metric_level": "KILO_PROJECT",
        "dimension": "system",
    })
    path = tmp_path / "extra.trug.json"
    path.write_text(json.dumps(graph))
    assert main(["trl", "decompile", str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "AGENT worker SHALL READ FILE input.\n"
    assert not captured.err
    restored = trl.compile(captured.out)
    assert validate(restored).valid
    expected = {**graph, "nodes": graph["nodes"][:-1]}
    assert _identity(restored) == _identity(expected)
