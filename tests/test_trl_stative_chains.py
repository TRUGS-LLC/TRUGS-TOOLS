# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import itertools
import json
import random

import pytest

from trugs_tools.lang_cli import main
from trugs_tools.validate import validate


def _identity(graph):
    return (
        sorted((n["id"], n["type"]) for n in graph["nodes"]),
        sorted((e["from_id"], e["to_id"], e["relation"]) for e in graph["edges"]),
    )


def _roundtrip(source, tmp_path, capsys):
    path = tmp_path / "source.trl"
    path.write_text(source)
    assert main(["trl", "compile", str(path)]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    graph = json.loads(captured.out)
    assert validate(graph).valid
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph))
    assert main(["trl", "decompile", str(path)]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    text = captured.out
    path = tmp_path / "restored.trl"
    path.write_text(text)
    assert main(["trl", "compile", str(path)]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    restored = json.loads(captured.out)
    assert validate(restored).valid
    assert _identity(restored) == _identity(graph)
    for node in graph["nodes"]:
        if node.get("properties", {}).get("defined"):
            definition = f'DEFINE "{node["id"]}" AS'
            mention = f'{node["type"]} {node["id"]}'
            if mention in text:
                assert text.index(definition) < text.index(mention)


@pytest.mark.parametrize("conjunction", ["THEN", "AND", "OR"])
def test_shared_stative_subject(conjunction, tmp_path, capsys):
    _roundtrip(
        'DEFINE "m" AS MODULE. AGENT a SHALL READ FILE input BOUNDED 1 '
        f'{conjunction} MODULE m CONTAINS FUNCTION f. '
        'AGENT b SHALL WRITE FILE output BOUNDED 1 '
        f'{conjunction} MODULE m REFERENCES MODULE peer.', tmp_path, capsys,
    )


@pytest.mark.parametrize("direction", ["forward", "backward", "cyclic"])
def test_defined_stative_targets(direction, tmp_path, capsys):
    source = 'DEFINE "m" AS MODULE. DEFINE "n" AS MODULE. '
    if direction != "backward":
        source += 'MODULE m REFERENCES MODULE n. '
    if direction != "forward":
        source += 'MODULE n REFERENCES MODULE m.'
    _roundtrip(source, tmp_path, capsys)


@pytest.mark.parametrize("conjunction", ["THEN", "OR"])
def test_stative_to_stative(conjunction, tmp_path, capsys):
    _roundtrip(
        'DEFINE "m" AS MODULE. DEFINE "n" AS MODULE. '
        'AGENT a SHALL READ FILE input THEN MODULE m CONTAINS FUNCTION f '
        f'{conjunction} MODULE n CONTAINS FUNCTION g.', tmp_path, capsys,
    )


def stative_sources():
    """Generate finite combinations of term types, targets and clause paths."""
    types = ("MODULE", "RECORD", "DATA")
    relations = ("CONTAINS", "REFERENCES", "DEPENDS_ON")
    for count in (1, 2, 3):
        for offset in range(3):
            terms = [(f"term{i}", types[(i + offset) % 3]) for i in range(count)]
            for order in itertools.permutations(terms):
                definitions = " ".join(f'DEFINE "{name}" AS {noun}.' for name, noun in order)
                for relation in relations:
                    for arity in (1, 2):
                        for targets in ("plain", "forward", "backward", "cyclic"):
                            if count == 1 and targets != "plain":
                                continue
                            clauses = []
                            for i, (name, noun) in enumerate(terms):
                                phrases = []
                                for j in range(arity):
                                    rel = relations[(relations.index(relation) + j) % 3]
                                    if targets == "plain":
                                        target = f"FILE leaf{i}_{j}"
                                    else:
                                        k = ((i + 1) % count if targets == "cyclic" else
                                             min(i + 1, count - 1) if targets == "forward" else max(i - 1, 0))
                                        other, other_type = terms[k]
                                        target = f"{other_type} {other}"
                                    phrases.append(f"{rel} {target}")
                                clauses.append(f'{noun} {name} ' + " ".join(phrases))
                            # Interleave definitions and sentences wherever all used
                            # terms have already been defined. Keep clause order fixed.
                            for positions in itertools.combinations(range(2 * count), count):
                                if positions == tuple(range(count)):
                                    continue
                                defined = set()
                                pieces = []
                                di = si = 0
                                for position in range(2 * count):
                                    if position in positions:
                                        name, noun = order[di]
                                        di += 1
                                        defined.add(name)
                                        pieces.append(f'DEFINE "{name}" AS {noun}.')
                                    else:
                                        clause = clauses[si]
                                        needed = {name for name, _ in terms if name in clause.split()}
                                        if not needed <= defined:
                                            break
                                        pieces.append(clause + ".")
                                        si += 1
                                else:
                                    yield ("interleaved", count, offset, tuple(n for n, _ in order), relation, arity, targets, positions), " ".join(pieces)
                            for style in ("standalone", "THEN", "AND", "OR", "chain-THEN", "chain-OR"):
                                for chains in (1, 2):
                                    if style == "standalone" and chains == 2:
                                        continue
                                    sentences = []
                                    for c in range(chains):
                                        if style == "standalone":
                                            sentences.extend(clause + "." for clause in clauses)
                                        elif style.startswith("chain-"):
                                            sentences.append((f" {style[6:]} ".join(clauses)) + ".")
                                        else:
                                            for i, clause in enumerate(clauses):
                                                sentences.append(f"AGENT actor{c}_{i} SHALL READ FILE input{c}_{i} BOUNDED 1 {style} {clause}.")
                                    label = (count, offset, tuple(n for n, _ in order), relation, arity, targets, style, chains)
                                    yield label, definitions + " " + " ".join(sentences)
    # Repeated subjects, conjunction multiplicity, branching and closed walks.
    definitions = 'DEFINE "m" AS MODULE. DEFINE "n" AS RECORD. DEFINE "d" AS DATA. '
    for conjunction in ("THEN", "OR"):
        for path in (("m", "n", "m"), ("m", "n", "d", "m"), ("m", "m")):
            nouns = {"m": "MODULE", "n": "RECORD", "d": "DATA"}
            clauses = [f'{nouns[name]} {name} REFERENCES FILE leaf{i}' for i, name in enumerate(path)]
            for copies in (1, 2):
                sentence = (f" {conjunction} ".join(clauses)) + "."
                yield ("walk", conjunction, path, copies), definitions + " ".join([sentence] * copies)
        yield ("branch", conjunction), definitions + (
            f'MODULE m REFERENCES FILE f {conjunction} RECORD n REFERENCES FILE g. '
            f'MODULE m REFERENCES FILE h {conjunction} DATA d REFERENCES FILE k.'
        )


    rng = random.Random(19)
    for case in range(1200):
        sentences = []
        serial = 0
        for _ in range(rng.randint(1, 4)):
            clauses = []
            for _ in range(rng.randint(1, 5)):
                if rng.randrange(3):
                    clauses.append(f'MODULE term{rng.randrange(3)} REFERENCES FILE leaf{serial}')
                else:
                    clauses.append(f'AGENT actor{serial} SHALL READ FILE input{serial} BOUNDED 1')
                serial += 1
            sentence = clauses[0]
            for clause in clauses[1:]:
                sentence += " " + rng.choice(("THEN", "OR")) + " " + clause
            sentences.append(sentence + ".")
        definitions = " ".join(f'DEFINE "term{i}" AS MODULE.' for i in range(3))
        yield ("mixed", case), definitions + " " + " ".join(sentences)

    for first, later in itertools.permutations(("MODULE", "RECORD", "DATA"), 2):
        for conjunction in ("THEN", "AND", "OR"):
            yield ("mention-type", first, later, conjunction), (
                f'DEFINE "m" AS MODULE. MODULE m REFERENCES {first} x. '
                f'AGENT a SHALL READ {later} x BOUNDED 1 {conjunction} MODULE m REFERENCES FILE y.'
            )


@pytest.mark.parametrize("preamble", ["", "WHEREAS "])
def test_stative_mixed_operation_order(preamble, tmp_path, capsys):
    _roundtrip(
        'DEFINE "m" AS MODULE. ' + preamble +
        'MODULE m REFERENCES FILE f THEN AGENT a SHALL READ FILE input. '
        'AGENT b SHALL WRITE FILE output THEN MODULE m REFERENCES FILE g.',
        tmp_path, capsys,
    )



def test_stative_first_mention_type(tmp_path, capsys):
    _roundtrip(
        'DEFINE "m" AS MODULE. MODULE m REFERENCES FILE x. '
        'AGENT a SHALL READ MODULE x THEN MODULE m REFERENCES FILE y.',
        tmp_path, capsys,
    )


def test_stative_corpus_sample(tmp_path, capsys):
    for index, (label, source) in enumerate(stative_sources()):
        if index % 233 == 0 or label[0] in ("walk", "branch"):
            _roundtrip(source, tmp_path, capsys)
