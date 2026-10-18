# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json

import pytest

from trugs_tools.lang_cli import main
from trugs_tools.validate import validate


def _identity(graph):
    return (
        sorted((n["id"], n["type"]) for n in graph["nodes"]),
        sorted((e["from_id"], e["to_id"], e["relation"]) for e in graph["edges"]),
    )


def _roundtrip(source, expected, tmp_path, capsys):
    source_path = tmp_path / "source.trl"
    source_path.write_text(source)
    assert main(["trl", "compile", str(source_path)]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    graph = json.loads(captured.out)
    assert validate(graph).valid
    graph_path = tmp_path / "graph.trug.json"
    graph_path.write_text(json.dumps(graph))
    assert main(["trl", "decompile", str(graph_path)]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    text = captured.out
    source_path.write_text(text)
    assert main(["trl", "compile", str(source_path)]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    restored = json.loads(captured.out)
    assert validate(restored).valid
    assert _identity(restored) == _identity(graph)
    assert text == expected


def test_defined_stative_standalone(tmp_path, capsys):
    _roundtrip(
        'DEFINE "m" AS MODULE. MODULE m CONTAINS FUNCTION f.',
        'DEFINE "m" AS MODULE.\nMODULE m CONTAINS FUNCTION f.\n',
        tmp_path, capsys,
    )


@pytest.mark.parametrize("conjunction", ["THEN", "AND", "OR"])
def test_defined_stative_continuation(conjunction, tmp_path, capsys):
    # The adverb ends the object list so AND joins clauses.
    _roundtrip(
        'DEFINE "m" AS MODULE. AGENT a SHALL READ FILE input BOUNDED 1 '
        f'{conjunction} MODULE m CONTAINS FUNCTION f.',
        'DEFINE "m" AS MODULE.\nAGENT a SHALL READ FILE input BOUNDED 1\n'
        f'  {conjunction} MODULE m CONTAINS FUNCTION f.\n',
        tmp_path, capsys,
    )


@pytest.mark.parametrize("relation, target", [
    ("CONTAINS", "FUNCTION f"),
    ("DEPENDS_ON", "MODULE peer"),
])
def test_defined_stative_then_text(relation, target, tmp_path, capsys):
    _roundtrip(
        'DEFINE "m" AS MODULE. AGENT a SHALL READ FILE input '
        f'THEN MODULE m {relation} {target}.',
        'DEFINE "m" AS MODULE.\nAGENT a SHALL READ FILE input\n'
        f'  THEN MODULE m {relation} {target}.\n',
        tmp_path, capsys,
    )


def test_defined_stative_standalone_and_continuation(tmp_path, capsys):
    _roundtrip(
        'DEFINE "m" AS MODULE. MODULE m CONTAINS FUNCTION f. '
        'AGENT a SHALL READ FILE input THEN MODULE m REFERENCES MODULE peer.',
        'DEFINE "m" AS MODULE.\nAGENT a SHALL READ FILE input\n'
        '  THEN MODULE m CONTAINS FUNCTION f REFERENCES MODULE peer.\n',
        tmp_path, capsys,
    )


@pytest.mark.parametrize("conjunction", [None, "THEN", "AND", "OR"])
def test_stative_before_definition_retains_compile_refusal(conjunction, tmp_path, capsys):
    prefix = (
        f"AGENT a SHALL READ FILE input BOUNDED 1 {conjunction} "
        if conjunction else ""
    )
    source_path = tmp_path / "source.trl"
    source_path.write_text(prefix + 'MODULE m CONTAINS FUNCTION f. DEFINE "m" AS MODULE.')
    assert main(["trl", "compile", str(source_path)]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "term 'm' already names a node" in captured.err
