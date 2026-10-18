# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import io
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


@pytest.mark.parametrize("source", [
    "PARTY api SHALL VALIDATE ALL ACTIVE RECORD.",
    "PARTY system SHALL VALIDATE ALL PENDING RECORD.",
    "PARTY client SHALL REQUEST PARTY server.\n"
    "PARTY server SHALL RESPOND PROMPTLY WITHIN 30s\n"
    "  OR PARTY client MAY RETRY BOUNDED 3\n"
    "  THEN HANDLE THE ERROR.",
    "NO PARTY SHALL WRITE CONFIDENTIAL RESOURCE\n"
    "  EXCEPT PARTY owner MAY WRITE CONFIDENTIAL RESOURCE\n"
    "    PROVIDED_THAT PARTY owner AUTHENTICATE TO SERVICE auth.",
], ids=["hello", "obligation", "request-response", "prohibition"])
def test_canonical_sentences_keep_concise_text(source):
    graph = trl.compile(source)
    assert trl.decompile(graph) == source


def test_repeated_actor_only_adds_necessary_identifiers():
    source = (
        "AGENT agent-1 SHALL READ FILE input THEN AGENT agent-1 SHALL WRITE FILE output.\n"
        "PARTY system SHALL VALIDATE ALL PENDING RECORD."
    )
    expected = (
        "AGENT agent-1 SHALL READ FILE input\n"
        "  THEN AGENT agent-1 SHALL WRITE FILE output.\n"
        "PARTY system SHALL VALIDATE ALL PENDING RECORD."
    )
    graph = trl.compile(source)
    text = trl.decompile(graph)
    assert text == expected
    assert _identity(trl.compile(text)) == _identity(graph)


@pytest.mark.parametrize("variant", ["contains-order", "noun-node-order", "metadata", "level"])
def test_structural_root_variants_keep_identity(variant, monkeypatch, capsys):
    graph = trl.compile("AGENT worker SHALL READ FILE input.")
    root = next(n for n in graph["nodes"] if n["type"] == "PROJECT")
    if variant == "contains-order":
        root["contains"].reverse()
    elif variant == "noun-node-order":
        graph["nodes"][0], graph["nodes"][2] = graph["nodes"][2], graph["nodes"][0]
    elif variant == "metadata":
        root["properties"]["purpose"] = "Structural root for compiled source"
    else:
        root["metric_level"] = "KILO_PROJECT"
    assert validate(graph).valid
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(graph)))
    assert main(["trl", "decompile", "-"]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    restored = trl.compile(captured.out)
    assert validate(restored).valid
    assert _identity(restored) == _identity(graph)
