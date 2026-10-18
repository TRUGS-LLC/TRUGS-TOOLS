# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import io
import json
import re
import textwrap
from pathlib import Path

from trugs_tools import trl
from trugs_tools.audit.extract_trl import audit_file, audit_path
from trugs_tools.lang_cli import main
from trugs_tools.validate import validate as core_validate


def _identity(graph):
    return (
        {(n["id"], n["type"]) for n in graph["nodes"]},
        {(e["from_id"], e["to_id"], e["relation"]) for e in graph["edges"]},
    )


def test_roundtrip_preserves_authored_actor_identifier():
    source = "AGENT agent-1 SHALL READ FILE input THEN AGENT agent-1 SHALL WRITE FILE output."
    graph = trl.compile(source)
    restored = trl.compile(trl.decompile(graph))
    assert _identity(restored) == _identity(graph)
    assert [n["id"] for n in restored["nodes"] if n["type"] == "AGENT"] == ["agent-1"]
    assert [e["from_id"] for e in restored["edges"] if e["relation"] == "SHALL"] == ["agent-1", "agent-1"]
    anonymous = trl.compile("AGENT SHALL READ FILE input THEN AGENT SHALL WRITE FILE output.")
    assert _identity(trl.compile(trl.decompile(anonymous))) == _identity(anonymous)


def test_roundtrip_preserves_defined_term_stative_edges():
    graph = trl.compile('DEFINE "m" AS MODULE. MODULE m CONTAINS FUNCTION f.')
    restored = trl.compile(trl.decompile(graph))
    assert ("m", "f", "CONTAINS") in _identity(restored)[1]
    assert _identity(restored) == _identity(graph)


def test_compile_success_is_core_valid_with_identifier_collisions(monkeypatch, capsys):
    sources = [
        ("AGENT op-1 SHALL READ FILE input.", None),
        ('DEFINE "x" AS RECORD. DEFINE "x" AS RECORD.', "x"),
        ('DEFINE "x" AS RECORD. DEFINE "x" AS FILE.', "x"),
        ("AGENT worker SHALL READ FILE input THEN AGENT op-1 SHALL WRITE FILE output.", None),
        ("AGENT SHALL READ FILE input THEN AGENT agent-1 SHALL WRITE FILE output.", None),
        ("AGENT worker SHALL READ FILE op-1 AND FILE op-2 TO FILE op-3 AND FILE op-4.", None),
        ('AGENT worker SHALL READ FILE input. DEFINE "op-1" AS RECORD.', None),
    ]
    for source, repeated_term in sources:
        monkeypatch.setattr("sys.stdin", io.StringIO(source))
        status = main(["trl", "compile", "-"])
        captured = capsys.readouterr()
        if status == 0:
            graph = json.loads(captured.out)
            assert core_validate(graph).valid
            assert len({n["id"] for n in graph["nodes"]}) == len(graph["nodes"])
            if repeated_term is None:
                assert _identity(trl.compile(trl.decompile(graph))) == _identity(graph)
        else:
            assert status == 1 and repeated_term is not None
            assert repeated_term in captured.err and "TRL" in captured.err
            assert not captured.out
    graph = trl.compile(sources[4][0])
    assert {n["id"] for n in graph["nodes"] if n["type"] == "AGENT"} == {"agent-1", "agent-2"}
    assert core_validate(trl.compile(trl.parse(sources[3][0]))).valid


def test_decompile_rejects_uncompilable_output(monkeypatch, capsys):
    root = Path(__file__).resolve().parents[1]
    assert main(["trl", "decompile", str(root / "first.trug.json")]) == 1
    captured = capsys.readouterr()
    assert "PROJECT" in captured.err and not captured.out
    graph = trl.compile("AGENT worker SHALL READ FILE input.")
    assert trl.compile(trl.decompile(graph))
    for change, word in [("relation", "UNKNOWN_RELATION"), ("operation", "UNKNOWN_VERB")]:
        broken = json.loads(json.dumps(graph))
        if change == "relation":
            broken["edges"].append({"from_id": "worker", "to_id": "input", "relation": word})
        else:
            next(n for n in broken["nodes"] if "operation" in n.get("properties", {}))["properties"]["operation"] = word
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(broken)))
        assert main(["trl", "decompile", "-"]) == 1
        captured = capsys.readouterr()
        assert word in captured.err and not captured.out


def test_markdown_language_applies_in_both_modes(tmp_path, capsys):
    language = json.loads(trl.DEFAULT_LANGUAGE_TRUG.read_text())
    language["nodes"] = [n for n in language["nodes"] if n.get("properties", {}).get("word") != "READ"]
    alternate = tmp_path / "alternate.language.trug.json"
    alternate.write_text(json.dumps(language))
    markdown = tmp_path / "read.md"
    markdown.write_text("<trl>AGENT worker SHALL READ FILE input.</trl>\n")
    for extra in ([], ["--all-errors"]):
        assert main(["audit", "markdown", str(markdown), "--language", str(alternate), *extra]) == 1
        captured = capsys.readouterr()
        assert "READ" in captured.out and "Error" in captured.out
    assert main(["audit", "markdown", str(markdown)]) == 0
    capsys.readouterr()
    lang = trl.load_language(str(alternate))
    assert audit_file(markdown).pass_count == 1
    assert audit_file(markdown, lang).fail_count == 1
    assert audit_path(tmp_path, lang)[0].fail_count == 1


def test_compilable_src_blocks_and_hello_roundtrip_skipping_noncompiling_blocks():
    """Extract all paired tags as in the corpus probe; skip blocks that do not compile."""
    root = Path(__file__).resolve().parents[1]
    sources = [("hello.trl", (root / "hello.trl").read_text())]
    for path in sorted((root / "src").rglob("*")):
        if not path.is_file() or path.suffix != ".py":
            continue
        text = path.read_text()
        for match in re.finditer(r"<trl>(.*?)</trl>", text, re.S):
            label = f"{path.relative_to(root)}:{text[:match.start()].count(chr(10)) + 1}"
            sources.append((label, textwrap.dedent(match.group(1)).strip()))
    checked = []
    differences = []
    for label, source in sources:
        try:
            graph = trl.compile(source)
        except trl.TRLError:
            continue
        checked.append(label)
        restored = trl.compile(trl.decompile(graph))
        if _identity(restored) != _identity(graph):
            differences.append(label)
    assert "hello.trl" in checked and len(checked) >= 10
    assert not differences, differences
