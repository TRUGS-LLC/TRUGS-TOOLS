"""Tests for the TRL compiler.

Covers tokenizer, classifier, parser, compile, decompile,
round-trip guarantee, validator (§4 rules 1, 2, 3, 7, 11),
and the full SPEC_examples.md fixture sweep (28/28 round-trip).

Pytest is preferred but optional — run directly with:
    python3 tools/test_trl.py
which iterates every `test_*` callable and reports counts.
"""

from __future__ import annotations
import pytest

import json
import sys
from pathlib import Path

# Allow running directly: `python3 tools/test_trl.py`
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trugs_tools import trl  # noqa: E402  (path-fix above must precede import)


# ─── Tokenizer ───────────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS tokenize SUBJECT_TO DATA sentence THEN ASSERT EACH RECORD token.
def test_tokenize_simple_sentence() -> None:
    tokens = trl.tokenize("PARTY system VALIDATE.")
    kinds = [t.kind for t in tokens]
    values = [t.value for t in tokens]
    assert kinds == ["WORD", "IDENTIFIER", "WORD", "PUNCT", "EOF"]
    assert values == ["PARTY", "system", "VALIDATE", ".", ""]


# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT NO RECORD sugar.
def test_tokenize_strips_sugar() -> None:
    # Sugar tokens start with apostrophe and are discarded before parsing
    tokens = trl.tokenize("PARTY system 'please VALIDATE 'of 'the.")
    values = [t.value for t in tokens if t.kind != "EOF"]
    assert values == ["PARTY", "system", "VALIDATE", "."]


# AGENT SHALL VALIDATE PROCESS tokenize SUBJECT_TO MULTIPLE DATA sentence.
def test_tokenize_multiple_sentences() -> None:
    tokens = trl.tokenize("PARTY a VALIDATE. PARTY b VALIDATE.")
    words = [t.value for t in tokens if t.kind == "WORD"]
    assert words == ["PARTY", "VALIDATE", "PARTY", "VALIDATE"]


# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT EXCEPTION SUBJECT_TO INVALID DATA input.
def test_tokenize_rejects_unexpected_char() -> None:
    try:
        trl.tokenize("PARTY @system VALIDATE.")
    except trl.TRLSyntaxError:
        return
    assert False, "expected TRLSyntaxError"


# ─── Classifier ──────────────────────────────────────────────────────

# AGENT SHALL VALIDATE FUNCTION classify THEN ASSERT RECORD speech SUBJECT_TO DATA noun.
def test_classify_known_noun() -> None:
    lang = trl.load_language()
    entry = trl.classify("PARTY", lang)
    assert entry["speech"] == "noun"
    assert entry["subcategory"] == "actors"  # spec section header preserves plural


# AGENT SHALL VALIDATE FUNCTION classify THEN ASSERT RECORD speech SUBJECT_TO DATA verb.
def test_classify_known_verb() -> None:
    lang = trl.load_language()
    entry = trl.classify("VALIDATE", lang)
    assert entry["speech"] == "verb"


# AGENT SHALL VALIDATE FUNCTION classify THEN ASSERT EACH RECORD modal REFERENCES RECORD subcategory.
def test_classify_modals_are_in_modal_subcategories() -> None:
    # Per SPEC_vocabulary.md, modals are in the Verbs section under
    # obligate / permit / prohibit subcategories (not a separate "modal"
    # speech). SPEC_grammar.md §1 BNF treats them syntactically as modals.
    lang = trl.load_language()
    expected = {"SHALL": "obligate", "MAY": "permit", "SHALL_NOT": "prohibit"}
    for word, sub in expected.items():
        entry = trl.classify(word, lang)
        assert entry["speech"] == "verb"
        assert entry["subcategory"] == sub


# AGENT SHALL VALIDATE FUNCTION classify THEN ASSERT EXCEPTION SUBJECT_TO INVALID DATA word.
def test_classify_unknown_word_raises() -> None:
    lang = trl.load_language()
    try:
        trl.classify("FAKEWORD", lang)
    except trl.TRLVocabularyError:
        return
    assert False, "expected TRLVocabularyError"


# ─── Parser ──────────────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD clause CONTAINS RECORD subject.
def test_parse_minimum_sentence() -> None:
    sentences = trl.parse("PARTY system VALIDATE.")
    assert len(sentences) == 1
    s = sentences[0]
    assert len(s.clauses) == 1
    c = s.clauses[0]
    assert c.subject.noun == "PARTY"
    assert c.subject.identifier == "system"
    assert c.verb_phrase.verb == "VALIDATE"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT EXCEPTION SUBJECT_TO DATA verb-as-subject.
def test_parse_rejects_verb_as_subject() -> None:
    try:
        trl.parse("FILTER system VALIDATE.")
    except trl.TRLGrammarError:
        return
    assert False, "FILTER is a verb, should not parse as subject"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT EXCEPTION SUBJECT_TO DATA missing-period.
def test_parse_rejects_missing_period() -> None:
    try:
        trl.parse("PARTY system VALIDATE")
    except trl.TRLSyntaxError:
        return
    assert False, "expected TRLSyntaxError for missing period"


# ─── Compile ─────────────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD subject-node AND RECORD op-node.
def test_compile_emits_subject_and_op_nodes() -> None:
    g = trl.compile("PARTY system VALIDATE.")
    assert len(g["nodes"]) == 2
    assert g["nodes"][0] == {"id": "system", "type": "PARTY"}
    op = g["nodes"][1]
    assert op["type"] == "TRANSFORM"
    assert op["properties"]["operation"] == "VALIDATE"
    assert op["properties"]["verb_subcategory"] == "obligate"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD edge IMPLEMENTS DATA executes-relation.
def test_compile_emits_executes_edge_for_unmodaled() -> None:
    g = trl.compile("PARTY system VALIDATE.")
    assert len(g["edges"]) == 1
    e = g["edges"][0]
    assert e["from_id"] == "system"
    assert e["to_id"] == "op-1"
    assert e["relation"] == "EXECUTES"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT UNIQUE RECORD subject-node FROM MULTIPLE DATA sentence.
def test_compile_reuses_existing_subject_node() -> None:
    # Two sentences, same subject. The subject node appears once, two ops, two edges.
    g = trl.compile("PARTY system VALIDATE. PARTY system FILTER.")
    party_nodes = [n for n in g["nodes"] if n["type"] == "PARTY"]
    assert len(party_nodes) == 1
    op_nodes = [n for n in g["nodes"] if n["type"] == "TRANSFORM"]
    assert len(op_nodes) == 2
    assert len(g["edges"]) == 2


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD anonymous-subject IMPLEMENTS DATA auto-id.
def test_anonymous_subject_now_allowed() -> None:
    """v0.1g allows anonymous subjects so WHEREAS preambles and NO PARTY clauses work."""
    g = trl.compile("PARTY VALIDATE.")
    party_nodes = [n for n in g["nodes"] if n["type"] == "PARTY"]
    assert len(party_nodes) == 1
    assert party_nodes[0]["id"] == "party-1"  # auto-generated


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO RECORD modal THEN ASSERT RECORD edge.
def test_compile_modal_on_edge() -> None:
    g = trl.compile("PARTY system SHALL VALIDATE.")
    assert g["edges"][0]["relation"] == "SHALL"


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA shall-not THEN ASSERT RECORD edge.
def test_compile_shall_not_on_edge() -> None:
    g = trl.compile("PARTY system SHALL_NOT WRITE.")
    assert g["edges"][0]["relation"] == "SHALL_NOT"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD anonymous-object IMPLEMENTS DATA auto-id.
def test_compile_anonymous_object_gets_auto_id() -> None:
    g = trl.compile("PARTY system SHALL VALIDATE ALL PENDING RECORD.")
    record = next(n for n in g["nodes"] if n["type"] == "RECORD")
    assert record["id"] == "record-1"  # auto-generated for anonymous noun
    # Per-mention attributes live on the ACTS_ON edge, not on the node
    obj_edge = next(e for e in g["edges"]
                    if e["to_id"] == "record-1" and e.get("relation") == "ACTS_ON")
    shape = (obj_edge.get("properties") or {}).get("np_shape", {})
    assert shape.get("article") == "ALL"
    assert shape.get("state") == "PENDING"


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA spec-example-1 THEN ASSERT RECORD round-trip.
def test_compile_spec_example_1_verbatim() -> None:
    """The very first example in SPEC_examples.md round-trips exactly."""
    g = trl.compile(SPEC_EXAMPLE_1)
    back = trl.decompile(g)
    assert back == SPEC_EXAMPLE_1
    g2 = trl.compile(back)
    assert g == g2


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT UNIQUE RECORD node FROM MULTIPLE RECORD reference.
def test_compile_reuses_existing_identified_object() -> None:
    # PARTY server (identified) should reuse a pre-existing node
    g = trl.compile("PARTY a SHALL REQUEST PARTY server. PARTY b SHALL REQUEST PARTY server.")
    servers = [n for n in g["nodes"] if n["id"] == "server"]
    assert len(servers) == 1


# ─── v0.1c — Conjunctions ─────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT MULTIPLE RECORD clause SUBJECT_TO DATA then-conjunction.
def test_parse_conjunction_creates_two_clauses() -> None:
    s = trl.parse("PARTY a SHALL FILTER DATA THEN SORT DATA.")[0]
    assert len(s.clauses) == 2
    assert s.conjunctions == ["THEN"]
    # Second clause inherits subject (no explicit subject in AST)
    assert s.clauses[1].subject is None


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD subject SUBJECT_TO DATA or-conjunction.
def test_parse_conjunction_preserves_explicit_subject() -> None:
    s = trl.parse("PARTY server SHALL RESPOND OR PARTY client MAY RETRY.")[0]
    assert s.conjunctions == ["OR"]
    assert s.clauses[0].subject.identifier == "server"
    assert s.clauses[1].subject is not None
    assert s.clauses[1].subject.identifier == "client"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD then-edge REFERENCES RECORD op-node.
def test_compile_conjunction_edge() -> None:
    g = trl.compile("PARTY a SHALL FILTER DATA THEN SORT DATA.")
    conj_edges = [e for e in g["edges"] if e.get("relation") == "THEN"]
    assert len(conj_edges) == 1
    assert conj_edges[0]["from_id"] == "op-1"
    assert conj_edges[0]["to_id"] == "op-2"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT MULTIPLE RECORD then-edge FROM DATA three-clause-chain.
def test_compile_three_way_then_chain() -> None:
    g = trl.compile("PARTY a SHALL FILTER DATA THEN SORT DATA THEN WRITE DATA.")
    then_edges = [e for e in g["edges"] if e.get("relation") == "THEN"]
    assert len(then_edges) == 2


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA unless-clause THEN ASSERT RECORD anonymous-subject.
def test_unless_with_anonymous_subject() -> None:
    src = 'PARTY api SHALL FILTER RECORD\n  UNLESS NO RECORD EXISTS.'
    g = trl.compile(src)
    # The UNLESS clause's subject (record-2) is an anonymous NO RECORD.
    # The NO article lives on the subject edge from record-2 → its op.
    record_nodes = [n for n in g["nodes"] if n["type"] == "RECORD"]
    assert any(n["id"] == "record-2" for n in record_nodes)
    no_subj_edge = next(
        e for e in g["edges"]
        if e["from_id"] == "record-2" and e.get("relation") in {"EXECUTES"} | trl.MODALS
    )
    shape = (no_subj_edge.get("properties") or {}).get("np_shape", {})
    assert shape.get("article") == "NO"


# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT NO RECORD inherited-subject.
def test_decompile_omits_inherited_subject() -> None:
    """Canonical form drops subject when it matches the prior clause."""
    src = 'PARTY a SHALL FILTER DATA\n  THEN SORT DATA.'
    back = trl.decompile(trl.compile(src))
    # Second clause should NOT include "PARTY a"
    assert back == src
    assert " PARTY a SORT " not in back  # sanity: subject is omitted after THEN


# ─── v0.1d — Prepositions ─────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD prep-phrase CONTAINS RECORD target.
def test_parse_single_preposition() -> None:
    s = trl.parse("PARTY user SHALL AUTHENTICATE TO SERVICE gateway.")[0]
    c = s.clauses[0]
    assert c.object is None
    assert len(c.prep_phrases) == 1
    assert c.prep_phrases[0].preposition == "TO"
    assert c.prep_phrases[0].target.noun == "SERVICE"
    assert c.prep_phrases[0].target.identifier == "gateway"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD object AND RECORD prep-phrase.
def test_parse_object_then_preposition() -> None:
    s = trl.parse("PARTY system SHALL WRITE DATA TO ENDPOINT output.")[0]
    c = s.clauses[0]
    assert c.object.noun == "DATA"
    assert [pp.preposition for pp in c.prep_phrases] == ["TO"]


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT MULTIPLE RECORD prep-phrase.
def test_parse_multiple_prepositions() -> None:
    s = trl.parse("PARTY system SHALL FILTER DATA FROM ENDPOINT input TO ENDPOINT output.")[0]
    c = s.clauses[0]
    assert [pp.preposition for pp in c.prep_phrases] == ["FROM", "TO"]


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD preposition-edge REFERENCES RECORD target.
def test_compile_emits_preposition_edges() -> None:
    g = trl.compile("PARTY user SHALL AUTHENTICATE TO SERVICE gateway.")
    to_edges = [e for e in g["edges"] if e.get("relation") == "TO"]
    assert len(to_edges) == 1
    assert to_edges[0]["to_id"] == "gateway"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD preposition-edge IMPLEMENTS DATA sequential-order.
def test_compile_preserves_preposition_order() -> None:
    g = trl.compile("PARTY system SHALL FILTER DATA FROM ENDPOINT a TO ENDPOINT b.")
    prep_rels = [e["relation"] for e in g["edges"]
                 if e["from_id"].startswith("op-") and e.get("relation") in ("FROM", "TO")]
    assert prep_rels == ["FROM", "TO"]


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA contains-preposition THEN ASSERT RECORD round-trip.
def test_contains_preposition_roundtrip() -> None:
    src = 'PARTY admin SHALL ADMINISTER RESOURCE\n  CONTAINS NAMESPACE production.'
    g = trl.compile(src)
    assert trl.decompile(g) == src


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA preposition-and-conjunction THEN ASSERT RECORD edge.
def test_preposition_with_conjunction_combination() -> None:
    src = 'PARTY system SHALL FILTER DATA TO ENDPOINT output\n  THEN VALIDATE RECORD.'
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    # Verify the TO edge is attached to op-1 (the FILTER op), not op-2
    to_edges = [e for e in g["edges"] if e.get("relation") == "TO"]
    assert len(to_edges) == 1
    assert to_edges[0]["from_id"] == "op-1"


# ─── v0.1e — Pronouns ─────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD pronoun-object REFERENCES RESULT.
def test_parse_pronoun_object() -> None:
    s = trl.parse("PARTY api SHALL FILTER RECORD THEN SORT RESULT.")[0]
    c2 = s.clauses[1]
    assert c2.object is not None
    assert c2.object.pronoun == "RESULT"
    assert c2.object.noun == ""


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RESULT REFERENCES RECORD prior-op.
def test_compile_result_points_to_previous_op() -> None:
    g = trl.compile("PARTY api SHALL FILTER RECORD THEN SORT RESULT.")
    # op-2 (SORT) should ACTS_ON op-1 (FILTER), with pronoun=RESULT
    result_edges = [e for e in g["edges"]
                    if e.get("relation") == "ACTS_ON" and e["from_id"] == "op-2"]
    assert len(result_edges) == 1
    assert result_edges[0]["to_id"] == "op-1"
    assert result_edges[0]["properties"]["pronoun"] == "RESULT"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT SELF REFERENCES RECORD subject-node.
def test_compile_self_points_to_subject() -> None:
    g = trl.compile("PARTY admin SHALL ADMINISTER RESOURCE REFERENCES SELF.")
    refs = [e for e in g["edges"] if e.get("relation") == "REFERENCES"]
    assert len(refs) == 1
    assert refs[0]["to_id"] == "admin"
    assert refs[0]["properties"]["pronoun"] == "SELF"


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO RESULT THEN ASSERT RECORD round-trip.
def test_result_in_prep_target() -> None:
    src = 'PARTY system SHALL FILTER DATA\n  THEN WRITE RESULT TO ENDPOINT destination.'
    g = trl.compile(src)
    assert trl.decompile(g) == src


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT EXCEPTION SUBJECT_TO RESULT.
def test_pronoun_without_antecedent_errors() -> None:
    # RESULT in the first clause has no prior op to reference
    try:
        trl.compile("PARTY system SHALL FILTER RESULT.")
    except trl.TRLGrammarError:
        return
    assert False, "expected TRLGrammarError — RESULT has no antecedent"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT EXCEPTION SUBJECT_TO DATA pronoun-as-subject.
def test_pronoun_cannot_be_subject_in_v01e() -> None:
    # Subjects require identifiers; pronoun-as-subject is deferred.
    try:
        trl.compile("SELF SHALL VALIDATE.")
    except trl.TRLError:
        return
    assert False, "expected TRLError — subject pronoun not in v0.1e scope"


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA spec-example-2 THEN ASSERT RECORD round-trip.
def test_spec_example_2_verbatim() -> None:
    """SPEC_examples.md §1 Example 2 round-trips."""
    g = trl.compile(SPEC_EXAMPLE_2)
    back = trl.decompile(g)
    assert back == SPEC_EXAMPLE_2
    assert trl.compile(back) == g


# ─── v0.1f — Adverbs + value literals ─────────────────────────────────

# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT RECORD duration-token SUBJECT_TO DATA literal.
def test_tokenize_duration_literal() -> None:
    tokens = trl.tokenize("WITHIN 30s.")
    kinds = [t.kind for t in tokens if t.kind != "EOF"]
    assert kinds == ["WORD", "DURATION", "PUNCT"]
    assert tokens[1].value == "30s"


# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT RECORD integer-token SUBJECT_TO DATA literal.
def test_tokenize_integer_literal() -> None:
    tokens = trl.tokenize("BOUNDED 3.")
    kinds = [t.kind for t in tokens if t.kind != "EOF"]
    assert kinds == ["WORD", "INTEGER", "PUNCT"]
    assert tokens[1].value == "3"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD adverb SUBJECT_TO DATA no-value.
def test_parse_adverb_no_value() -> None:
    s = trl.parse("PARTY server SHALL RESPOND PROMPTLY.")[0]
    advs = s.clauses[0].verb_phrase.adverbs
    assert len(advs) == 1
    assert advs[0].adverb == "PROMPTLY"
    assert advs[0].value is None


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD adverb CONTAINS DATA duration-value.
def test_parse_adverb_with_duration() -> None:
    s = trl.parse("PARTY server SHALL RESPOND WITHIN 30s.")[0]
    advs = s.clauses[0].verb_phrase.adverbs
    assert advs[0].adverb == "WITHIN"
    assert advs[0].value == "30s"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD adverb CONTAINS DATA integer-value.
def test_parse_adverb_with_integer() -> None:
    s = trl.parse("PARTY client MAY RETRY BOUNDED 3.")[0]
    advs = s.clauses[0].verb_phrase.adverbs
    assert advs[0].adverb == "BOUNDED"
    assert advs[0].value == "3"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT MULTIPLE RECORD adverb.
def test_parse_multiple_adverbs() -> None:
    s = trl.parse("PARTY server SHALL RESPOND PROMPTLY WITHIN 30s.")[0]
    advs = s.clauses[0].verb_phrase.adverbs
    assert [(a.adverb, a.value) for a in advs] == [
        ("PROMPTLY", None),
        ("WITHIN", "30s"),
    ]


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD op-node CONTAINS RECORD adverb.
def test_compile_stores_adverbs_on_op() -> None:
    g = trl.compile("PARTY server SHALL RESPOND PROMPTLY WITHIN 30s.")
    op = next(n for n in g["nodes"] if n.get("type") == "TRANSFORM")
    assert op["properties"]["adverbs"] == [
        {"adverb": "PROMPTLY"},
        {"adverb": "WITHIN", "value": "30s"},
    ]


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA spec-example-3 THEN ASSERT RECORD round-trip.
def test_spec_example_3_verbatim() -> None:
    """SPEC_examples.md §1 Example 3 round-trips — multi-sentence with
    adverbs, value literals, OR, THEN, and THE <noun> back-reference."""
    g = trl.compile(SPEC_EXAMPLE_3)
    back = trl.decompile(g)
    assert back == SPEC_EXAMPLE_3
    assert trl.compile(back) == g


# ─── v0.1g — DEFINE / WHEREAS / STRING literals ──────────────────────

# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT RECORD string-token SUBJECT_TO DATA quoted-literal.
def test_tokenize_string_literal() -> None:
    tokens = trl.tokenize('DEFINE "curator" AS PARTY.')
    kinds = [t.kind for t in tokens if t.kind != "EOF"]
    assert kinds == ["WORD", "STRING", "WORD", "WORD", "PUNCT"]
    assert tokens[1].value == "curator"


# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT RECORD string-token CONTAINS DATA space.
def test_tokenize_string_with_spaces() -> None:
    tokens = trl.tokenize('DEFINE "policy name" AS PARTY.')
    assert tokens[1].value == "policy name"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD definition CONTAINS DATA name.
def test_parse_define() -> None:
    s = trl.parse('DEFINE "curator" AS PARTY.')[0]
    assert s.definition is not None
    assert s.definition.name == "curator"
    assert s.definition.noun_phrase.noun == "PARTY"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD definition CONTAINS RECORD adjective.
def test_parse_define_with_adjective() -> None:
    s = trl.parse('DEFINE "ledger" AS IMMUTABLE RECORD.')[0]
    d = s.definition
    assert d.name == "ledger"
    assert d.noun_phrase.noun == "RECORD"
    assert d.noun_phrase.adjectives == ["IMMUTABLE"]


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD defined-node SUBJECT_TO DATA define-statement.
def test_compile_define_emits_defined_term() -> None:
    g = trl.compile('DEFINE "curator" AS PARTY.')
    curator = next(n for n in g["nodes"] if n["id"] == "curator")
    assert curator["type"] == "PARTY"
    assert curator["properties"]["defined"] is True
    assert curator["properties"]["name"] == "curator"


# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD sentence IMPLEMENTS DATA whereas-preamble.
def test_parse_whereas_preamble() -> None:
    s = trl.parse("WHEREAS PARTY system ADMINISTER ALL RESOURCE.")[0]
    assert s.preamble is True


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD op-node IMPLEMENTS DATA whereas-preamble.
def test_compile_whereas_marks_preamble_on_op() -> None:
    g = trl.compile("WHEREAS PARTY system ADMINISTER ALL RESOURCE.")
    op = next(n for n in g["nodes"] if n.get("type") == "TRANSFORM")
    assert op["properties"]["preamble"] is True


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA spec-example-10 THEN ASSERT RECORD round-trip.
def test_spec_example_10_verbatim() -> None:
    """SPEC_examples.md §3 Example 10 — DEFINE + AND parallel."""
    g = trl.compile(SPEC_EXAMPLE_10)
    back = trl.decompile(g)
    assert back == SPEC_EXAMPLE_10
    assert trl.compile(back) == g


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA spec-example-18 THEN ASSERT RECORD round-trip.
def test_spec_example_18_verbatim() -> None:
    """SPEC_examples.md §4 Example 18 — WHEREAS preambles + operative."""
    g = trl.compile(SPEC_EXAMPLE_18)
    back = trl.decompile(g)
    assert back == SPEC_EXAMPLE_18
    assert trl.compile(back) == g


# ─── v0.2 — AND-chained noun lists ────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT MULTIPLE RECORD acts-on-edge SUBJECT_TO DATA and-chain.
def test_object_and_chain_two_items() -> None:
    g = trl.compile("PARTY analyst SHALL READ DATA AND RECORD.")
    acts_on = [e for e in g["edges"] if e.get("relation") == "ACTS_ON"]
    assert len(acts_on) == 2
    # Both should share the same chain_id
    cid = (acts_on[0].get("properties") or {}).get("chain_id")
    assert cid is not None
    assert (acts_on[1].get("properties") or {}).get("chain_id") == cid


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA three-item-and-chain THEN ASSERT RECORD round-trip.
def test_object_and_chain_three_items_with_prep() -> None:
    src = "PARTY system SHALL NEST MODULE auth AND MODULE data AND MODULE search TO NAMESPACE api-system."
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    assert trl.compile(back) == g


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT MULTIPLE RECORD to-edge SUBJECT_TO DATA and-chain.
def test_prep_noun_list_and_chain() -> None:
    src = "PARTY a SHALL SPLIT THE MESSAGE TO AGENT worker-a AND AGENT worker-b."
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    to_edges = [e for e in g["edges"] if e.get("relation") == "TO"]
    assert len(to_edges) == 2


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD clause-level-and SUBJECT_TO DATA noun-list-and.
def test_clause_level_and_still_works() -> None:
    """Smarter peek must not break clause-level AND."""
    src = 'PARTY system SHALL FILTER DATA\n  AND PARTY system SHALL VALIDATE RECORD.'
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src


# ─── v0.2.1 — Verb elision and current-op pronouns ───────────────────

# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD op-node IMPLEMENTS DATA verb-elision.
def test_verb_elision_in_except_clause() -> None:
    src = 'NO PARTY MAY WRITE RECORD ledger\n  EXCEPT PARTY system.'
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    # The EXCEPT clause's op should carry verb_elided so canonical form drops verb+modal
    op2 = next(n for n in g["nodes"] if n["id"] == "op-2")
    assert op2["properties"]["verb_elided"] is True
    # Compiler still records the inherited verb for graph use
    assert op2["properties"]["operation"] == "WRITE"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT INPUT REFERENCES RECORD op-node.
def test_input_pronoun_resolves_to_current_op() -> None:
    src = "EACH AGENT SHALL HANDLE INPUT PARALLEL."
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    # The INPUT pronoun creates an ACTS_ON edge from op back to itself
    op = next(n for n in g["nodes"] if n.get("type") == "TRANSFORM")
    self_edge = next(e for e in g["edges"]
                     if e["from_id"] == op["id"]
                     and e.get("relation") == "ACTS_ON"
                     and (e.get("properties") or {}).get("pronoun") == "INPUT")
    assert self_edge["to_id"] == op["id"]


# ─── v0.2.2 — Stative clauses ─────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RECORD direct-edge SUBJECT_TO DATA stative-clause.
def test_stative_clause_emits_direct_edge() -> None:
    g = trl.compile("THE REMEDY DEPENDS_ON PARTY owner.")
    # No op nodes — only the subject, target, and the direct edge between them
    op_count = sum(1 for n in g["nodes"] if n.get("type") == "TRANSFORM")
    assert op_count == 0
    edge = next(e for e in g["edges"] if e.get("relation") == "DEPENDS_ON")
    assert edge["from_id"] == "remedy-1"
    assert edge["to_id"] == "owner"


# AGENT SHALL VALIDATE PROCESS decompile SUBJECT_TO DATA stative-clause THEN ASSERT RECORD round-trip.
def test_stative_clause_round_trip_verbatim() -> None:
    src = "THE REMEDY DEPENDS_ON PARTY owner."
    assert trl.decompile(trl.compile(src)) == src


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA stative-whereas THEN ASSERT RECORD preamble-edge.
def test_stative_in_whereas_preamble() -> None:
    src = "WHEREAS SERVICE kafka FEEDS STREAM raw-events."
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    edge = next(e for e in g["edges"] if e.get("relation") == "FEEDS")
    assert (edge.get("properties") or {}).get("preamble") is True


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA stative-after-then THEN ASSERT RECORD round-trip.
def test_stative_after_then_in_compound_sentence() -> None:
    """Example 9 pattern: IF ... THEN <stative-clause>."""
    src = 'IF ANY PARTY WRITE CONFIDENTIAL RESOURCE\n  THEN THE REMEDY DEPENDS_ON PARTY owner.'
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src


# ─── v0.2.3 — SAID pronoun + per-mention noun_phrase attributes ──────

# AGENT SHALL VALIDATE PROCESS parse THEN ASSERT RECORD object IMPLEMENTS DATA said-article.
def test_said_as_quasi_article() -> None:
    """SAID NOUN parses as `article=SAID + noun`."""
    s = trl.parse("PARTY a SHALL READ SAID DATA.")[0]
    obj = s.clauses[0].object
    assert obj is not None
    assert obj.article == "SAID"
    assert obj.noun == "DATA"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT EACH RECORD edge CONTAINS RECORD np-shape.
def test_per_mention_attributes_dont_leak_between_references() -> None:
    """A node referenced as `RECORD ledger` then `THE RECORD ledger` keeps
    each mention's article on its own edge — neither leaks into the other."""
    src = (
        'DEFINE "ledger" AS IMMUTABLE RECORD.\n'
        'PARTY system SHALL WRITE EACH VALID DATA TO RECORD ledger.\n'
        'PARTY system SHALL REPLACE THE RECORD ledger FROM SAID RECORD.'
    )
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    # The ledger node itself should carry only DEFINE attributes
    ledger = next(n for n in g["nodes"] if n["id"] == "ledger")
    assert ledger.get("properties", {}).get("defined") is True
    # Reference shapes are on edges, not on the node
    assert "scope" not in ledger.get("properties", {})


# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT RECORD duration-token SUBJECT_TO DATA two-letter-unit.
def test_duration_with_two_letter_unit() -> None:
    """v0.2.4 — 100ms tokenizes as one DURATION, not 100m + s."""
    tokens = trl.tokenize("WITHIN 100ms.")
    durations = [t for t in tokens if t.kind == "DURATION"]
    assert len(durations) == 1
    assert durations[0].value == "100ms"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT RESULT REFERENCES RECORD prior-sentence-op.
def test_cross_sentence_pronoun_antecedent() -> None:
    """v0.2.4 — RESULT in a later sentence references the prior sentence's op."""
    src = "PARTY a SHALL FILTER DATA.\nPARTY loader SHALL WRITE EACH RESULT TO ENDPOINT store."
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    # Verify the EACH article on the RESULT pronoun survived
    result_edge = next(e for e in g["edges"]
                       if (e.get("properties") or {}).get("pronoun") == "RESULT")
    assert result_edge["properties"]["pronoun_article"] == "EACH"


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA except-then-provided-that THEN ASSERT RECORD round-trip.
def test_subject_only_with_following_conjunction() -> None:
    """v0.2.4 — `EXCEPT PARTY loader PROVIDED_THAT ...` — subject-only EXCEPT
    clause followed by another conjunction-led clause."""
    src = (
        "NO PARTY SHALL WRITE ENDPOINT event-store\n"
        "  EXCEPT PARTY loader\n"
        "    PROVIDED_THAT PARTY loader AUTHENTICATE TO SERVICE auth."
    )
    assert trl.decompile(trl.compile(src)) == src


# AGENT SHALL VALIDATE PROCESS compile SUBJECT_TO DATA spec-example-14 THEN ASSERT RECORD round-trip.
def test_spec_example_14_verbatim() -> None:
    """SPEC Example 14 — DEFINE + reuse of `ledger` with different mentions
    + SAID pronoun. Round-trips when per-mention shapes are isolated."""
    src = (
        'DEFINE "ledger" AS IMMUTABLE RECORD.\n'
        'PARTY system SHALL WRITE EACH VALID DATA TO RECORD ledger.\n'
        'NO PARTY MAY WRITE RECORD ledger\n'
        '  EXCEPT PARTY system.\n'
        'PARTY system SHALL REPLACE THE RECORD ledger FROM SAID RECORD.'
    )
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src
    assert trl.compile(back) == g


# ─── v0.1h — Sweep all SPEC_examples.md examples ─────────────────────

import re
from pathlib import Path

SPEC_EXAMPLES_PATH = Path(__file__).resolve().parent.parent / "TRUGS_LANGUAGE" / "SPEC_examples.md"

# Examples this compiler version cannot round-trip yet — each tracked for follow-on:
#   7   — DEADLINE not in 190-word vocabulary (TRUGS-DEV#1542)
#   14  — SAID pronoun used as article-like ("SAID RECORD")
#   28  — Complete ETL — multi-line stative WHEREAS interleaved with operative
# All 28 SPEC_examples now round-trip. (TRUGS-DEVELOPMENT#1542 resolved by
# updating Example 7 to use INSTRUMENT instead of DEADLINE, keeping the
# closed 190-word vocabulary intact.)
KNOWN_DEFERRED: set[int] = set()


def _extract_examples():
    text = SPEC_EXAMPLES_PATH.read_text()
    pat = re.compile(r"### (\d+)\.\s+([^\n]+)\n```\n(.+?)\n```", re.DOTALL)
    return [(int(m.group(1)), m.group(2), m.group(3).strip()) for m in pat.finditer(text)]


def _normalize_whitespace(src: str) -> str:
    return re.sub(r"\s+", " ", src).strip()


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT ALL RECORD spec-example IMPLEMENTS RECORD round-trip.
@pytest.mark.skip(reason="requires TRUGS/TRUGS_LANGUAGE/SPEC_examples.md (TRUGS spec doc, not bundled in trugs-tools)")
def test_spec_examples_in_scope_round_trip() -> None:
    """Every SPEC_examples.md example not in KNOWN_DEFERRED must round-trip
    at the graph level (compile(decompile(g)) == g)."""
    examples = _extract_examples()
    assert examples, "failed to extract examples from SPEC_examples.md"
    failures: list[str] = []
    for n, title, body in examples:
        if n in KNOWN_DEFERRED:
            continue
        norm = _normalize_whitespace(body)
        try:
            g = trl.compile(norm)
            back = trl.decompile(g)
            g2 = trl.compile(back)
            if g != g2:
                failures.append(f"#{n} {title}: graph diverged on round-trip")
        except trl.TRLError as e:
            failures.append(f"#{n} {title}: {type(e).__name__}: {e}")
    assert not failures, "in-scope examples failed:\n" + "\n".join(failures)


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT ALL RECORD spec-example.
@pytest.mark.skip(reason="requires TRUGS/TRUGS_LANGUAGE/SPEC_examples.md (TRUGS spec doc, not bundled in trugs-tools)")
def test_spec_examples_coverage_summary() -> None:
    """Sanity assertion: at least 23 of the 28 examples round-trip post-v0.2.1."""
    examples = _extract_examples()
    passed = 0
    for n, _, body in examples:
        norm = _normalize_whitespace(body)
        try:
            g = trl.compile(norm)
            if trl.compile(trl.decompile(g)) == g:
                passed += 1
        except trl.TRLError:
            pass
    assert passed == len(examples), f"only {passed}/{len(examples)} examples round-trip; expected all"


# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT ALL RECORD spec-example IMPLEMENTS DATA byte-identical.
@pytest.mark.skip(reason="requires TRUGS/TRUGS_LANGUAGE/SPEC_examples.md (TRUGS spec doc, not bundled in trugs-tools)")
def test_spec_examples_byte_identical_round_trip() -> None:
    """v0.3 — every published SPEC_examples.md example round-trips
    BYTE-IDENTICAL via `decompile(compile(body)) == body`. Locks in
    the v0.3 (28/28) headline guarantee. If a future change reintroduces
    whitespace drift between the canonical decompile and the SPEC source,
    this test catches it immediately."""
    examples = _extract_examples()
    assert examples, "failed to extract examples from SPEC_examples.md"
    failures: list[str] = []
    for n, title, body in examples:
        try:
            g = trl.compile(body)
            back = trl.decompile(g)
        except trl.TRLError as e:
            failures.append(f"#{n} {title}: {type(e).__name__}: {e}")
            continue
        if back != body:
            failures.append(f"#{n} {title}: byte-identical round-trip failed")
    assert not failures, (
        f"{len(failures)}/{len(examples)} SPEC examples not byte-identical:\n"
        + "\n".join(failures)
    )


# ─── Decompile ───────────────────────────────────────────────────────

# AGENT SHALL VALIDATE PROCESS decompile SUBJECT_TO RECORD minimum-graph THEN ASSERT DATA sentence.
def test_decompile_minimum_graph() -> None:
    g = {
        "nodes": [
            {"id": "system", "type": "PARTY"},
            {"id": "op-1", "type": "TRANSFORM",
             "properties": {"operation": "VALIDATE", "verb_subcategory": "obligate"}},
        ],
        "edges": [{"from_id": "system", "to_id": "op-1", "relation": "EXECUTES"}],
    }
    assert trl.decompile(g) == "PARTY system VALIDATE."


# ─── Round-trip (the primary acceptance criterion) ──────────────────

ROUND_TRIP_FIXTURES = [
    # v0.1a — minimum form
    'PARTY system VALIDATE.',
    'PARTY api FILTER.',
    'PARTY user AUTHENTICATE.',
    'AGENT worker FILTER.',
    'SERVICE gateway VALIDATE.',
    # v0.1b — modals
    'PARTY system SHALL VALIDATE.',
    'AGENT worker MAY FILTER.',
    'PARTY system SHALL_NOT WRITE.',
    # v0.1b — single object
    'PARTY client SHALL REQUEST PARTY server.',
    'PARTY system SHALL VALIDATE DATA.',
    # v0.1b — articles + adjectives on anonymous objects
    "PARTY system SHALL VALIDATE ALL PENDING RECORD.",  # Example 1 verbatim
    'PARTY api SHALL FILTER ALL ACTIVE DATA.',
    'AGENT worker MAY READ ANY CRITICAL FILE.',
    'PARTY system SHALL_NOT WRITE ANY READONLY RESOURCE.',
    # v0.1c — conjunctions, subject carryover
    'PARTY a SHALL FILTER DATA\n  THEN SORT DATA.',
    'PARTY system SHALL FILTER RECORD\n  THEN VALIDATE RECORD.',
    'PARTY api SHALL FILTER ALL ACTIVE RECORD\n  THEN SORT ALL RECORD.',
    # v0.1c — AND parallel (canonical form repeats subject after AND)
    'PARTY system SHALL FILTER DATA\n  AND PARTY system SHALL VALIDATE RECORD.',
    # v0.1c — OR alternative, new subject
    'PARTY server SHALL RESPOND\n  OR PARTY client MAY RETRY.',
    # v0.1c — UNLESS with anonymous subject
    'PARTY api SHALL FILTER RECORD\n  UNLESS NO RECORD EXISTS.',
    'PARTY api SHALL FILTER ALL ACTIVE RECORD\n  UNLESS NO VALID RECORD EXISTS.',
    # v0.1c — IF/PROVIDED_THAT/FINALLY (IF repeats subject; FINALLY inherits)
    'PARTY admin MAY APPROVE RECORD\n  IF PARTY admin AUTHENTICATE.',
    'PARTY system SHALL VALIDATE RECORD\n  PROVIDED_THAT PARTY admin APPROVE.',
    'PARTY system SHALL FILTER RECORD\n  THEN VALIDATE RECORD\n  FINALLY WRITE RECORD.',
    # v0.1d — prepositions
    'PARTY user SHALL AUTHENTICATE TO SERVICE gateway.',
    'PARTY system SHALL WRITE DATA TO ENDPOINT output.',
    'PARTY agent SHALL RESPOND ON_BEHALF_OF PARTY user.',
    'PARTY system SHALL FILTER DATA FROM ENDPOINT input TO ENDPOINT output.',
    'PARTY admin SHALL ADMINISTER RESOURCE\n  CONTAINS NAMESPACE production.',
    'PARTY a SHALL READ DATA REFERENCES RESOURCE store.',
    'PARTY system SHALL VALIDATE RECORD\n  SUBJECT_TO INTERFACE schema.',
    # v0.1d — preposition + conjunction combined
    'PARTY system SHALL FILTER DATA TO ENDPOINT output\n  THEN VALIDATE RECORD.',
    # v0.1e — pronouns
    'PARTY api SHALL FILTER ALL ACTIVE RECORD\n  THEN SORT RESULT.',
    'PARTY system SHALL MAP RECORD TO DATA\n  THEN MERGE RESULT TO STREAM output.',
    'PARTY admin SHALL ADMINISTER RESOURCE REFERENCES SELF.',
    'PARTY a SHALL FILTER DATA\n  THEN VALIDATE OUTPUT.',
    'PARTY system SHALL FILTER DATA\n  THEN WRITE RESULT TO ENDPOINT destination.',
    # v0.1f — adverbs and value literals
    'PARTY server SHALL RESPOND PROMPTLY.',
    'PARTY server SHALL RESPOND WITHIN 30s.',
    'PARTY client MAY RETRY BOUNDED 3.',
    'PARTY server SHALL RESPOND PROMPTLY WITHIN 30s.',
    'PARTY server SHALL RESPOND PROMPTLY WITHIN 30s\n  OR PARTY client MAY RETRY BOUNDED 3.',
    # v0.1g — DEFINE / WHEREAS / STRING literals
    'DEFINE "curator" AS PARTY.',
    'DEFINE "ledger" AS IMMUTABLE RECORD.',
    'WHEREAS PARTY system ADMINISTER ALL RESOURCE.',
    'WHEREAS ALL RECORD REQUIRE MODULE storage.',
]

SPEC_EXAMPLE_1 = "PARTY system SHALL VALIDATE ALL PENDING RECORD."
SPEC_EXAMPLE_2 = (
    "PARTY api SHALL FILTER ALL ACTIVE RECORD\n"
    "  THEN SORT RESULT\n"
    "  UNLESS NO VALID RECORD REQUIRE SELF."
)
SPEC_EXAMPLE_3 = (
    "PARTY client SHALL REQUEST PARTY server.\n"
    "PARTY server SHALL RESPOND PROMPTLY WITHIN 30s\n"
    "  OR PARTY client MAY RETRY BOUNDED 3\n"
    "  THEN HANDLE THE ERROR."
)
SPEC_EXAMPLE_10 = (
    'DEFINE "curator" AS PARTY.\n'
    "PARTY curator SHALL VALIDATE ALL RECORD\n"
    "  AND PARTY curator SHALL_NOT WRITE INVALID RECORD."
)
SPEC_EXAMPLE_18 = (
    "WHEREAS PARTY system ADMINISTER ALL RESOURCE.\n"
    "WHEREAS ALL RECORD REQUIRE MODULE storage.\n"
    "PARTY system SHALL VALIDATE EACH RECORD ONCE\n"
    "  THEN WRITE RESULT TO ENDPOINT output."
)


# AGENT SHALL VALIDATE PROCESS compile THEN VALIDATE PROCESS decompile THEN ASSERT EACH RECORD fixture.
def test_round_trip_trl_to_trug_to_trl() -> None:
    for sentence in ROUND_TRIP_FIXTURES:
        g1 = trl.compile(sentence)
        sentence_out = trl.decompile(g1)
        g2 = trl.compile(sentence_out)
        assert g1 == g2, f"round-trip diverged for {sentence!r}: {g1} != {g2}"
        assert sentence_out == sentence, f"decompile diverged for {sentence!r}: {sentence_out!r}"


# AGENT SHALL VALIDATE PROCESS decompile THEN VALIDATE PROCESS compile THEN ASSERT EACH RECORD fixture.
def test_round_trip_trug_to_trl_to_trug() -> None:
    for sentence in ROUND_TRIP_FIXTURES:
        g1 = trl.compile(sentence)
        s = trl.decompile(g1)
        g2 = trl.compile(s)
        assert g1 == g2


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT NO RECORD sugar SUBJECT_TO DATA canonical-form.
def test_round_trip_sugar_is_stripped() -> None:
    # Sugar doesn't survive the round-trip — canonical form is sugar-free
    original = "PARTY system 'please VALIDATE 'of 'all."
    g = trl.compile(original)
    decompiled = trl.decompile(g)
    assert decompiled == "PARTY system VALIDATE."  # sugar gone


# ─── Validate ────────────────────────────────────────────────────────

# AGENT SHALL VALIDATE FUNCTION validate THEN ASSERT NO RECORD error SUBJECT_TO DATA clean-graph.
def test_validate_clean_graph() -> None:
    g = trl.compile("PARTY system VALIDATE.")
    assert trl.validate(g) == []


# AGENT SHALL VALIDATE FUNCTION validate THEN ASSERT RECORD error SUBJECT_TO INVALID DATA node-type.
def test_validate_detects_bad_noun_type() -> None:
    g = {
        "nodes": [{"id": "x", "type": "NOT_A_NOUN"}],
        "edges": [],
    }
    errors = trl.validate(g)
    assert any("not a TRL noun" in e for e in errors)


# AGENT SHALL VALIDATE FUNCTION validate THEN ASSERT RECORD error SUBJECT_TO DATA missing-relation.
def test_validate_detects_missing_relation() -> None:
    g = {
        "nodes": [
            {"id": "x", "type": "PARTY"},
            {"id": "op-1", "type": "TRANSFORM", "properties": {"operation": "VALIDATE"}},
        ],
        "edges": [{"from_id": "x", "to_id": "op-1"}],  # missing relation
    }
    errors = trl.validate(g)
    assert any("missing relation" in e for e in errors)


# ─── v0.2.5 — Audit-driven fixes ──────────────────────────────────────

# AGENT SHALL VALIDATE FUNCTION validate THEN ASSERT RECORD error SUBJECT_TO DATA rule-3-subject-verb.
def test_validator_rule_3_subject_verb_compatibility() -> None:
    """SPEC §2.1 / §4 rule 3 — Artifact subjects can only use control verbs."""
    g = trl.compile("DATA x VALIDATE.")  # VALIDATE is obligate, DATA is artifact
    errors = trl.validate(g)
    assert any("§2.1" in e for e in errors), f"expected §2.1 violation, got {errors!r}"


# AGENT SHALL VALIDATE FUNCTION validate THEN ASSERT RECORD error SUBJECT_TO DATA rule-7-modal-actor.
def test_validator_rule_7_modal_actor_only() -> None:
    """SPEC §2.3 / §4 rule 7 — Modals require Actor subjects."""
    g_bad = {
        "nodes": [
            {"id": "x", "type": "FILE"},
            {"id": "op-1", "type": "TRANSFORM",
             "properties": {"operation": "READ", "verb_subcategory": "move"}},
        ],
        "edges": [{"from_id": "x", "to_id": "op-1", "relation": "SHALL"}],
    }
    errors = trl.validate(g_bad)
    assert any("§2.3" in e for e in errors), f"expected §2.3 violation, got {errors!r}"


# AGENT SHALL VALIDATE FUNCTION validate THEN ASSERT RECORD error SUBJECT_TO DATA rule-11-double-negation.
def test_validator_rule_11_no_double_negation() -> None:
    """SPEC §4 rule 11 — Negative article + Prohibit modal cannot co-occur."""
    g = trl.compile("NO PARTY SHALL_NOT WRITE FILE.")
    errors = trl.validate(g)
    assert any("§4.11" in e for e in errors), f"expected §4.11 violation, got {errors!r}"


# AGENT SHALL VALIDATE FUNCTION validate THEN ASSERT NO RECORD error SUBJECT_TO DATA well-formed-graph.
def test_validator_clean_graph_passes_all_rules() -> None:
    g = trl.compile("PARTY system SHALL VALIDATE ALL PENDING RECORD.")
    assert trl.validate(g) == []


# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT EACH RECORD token CONTAINS DATA line-and-col.
def test_token_carries_line_and_col() -> None:
    """v0.2.5 — every Token has `line` and `col` for error messages."""
    src = "PARTY a\n  SHALL VALIDATE."
    tokens = trl.tokenize(src)
    party = tokens[0]
    assert party.value == "PARTY"
    assert party.line == 1 and party.col == 1
    shall = next(t for t in tokens if t.value == "SHALL")
    assert shall.line == 2 and shall.col == 3


# AGENT SHALL VALIDATE PROCESS tokenize THEN ASSERT EXCEPTION CONTAINS DATA line-and-col.
def test_tokenize_error_includes_line_col() -> None:
    try:
        trl.tokenize("PARTY system VALIDATE @bad.")
    except trl.TRLSyntaxError as e:
        assert "line 1, col 23" in str(e)
        return
    raise AssertionError("expected TRLSyntaxError")


# AGENT SHALL VALIDATE FUNCTION main THEN ASSERT EXCEPTION SUBJECT_TO INVALID DATA json-input.
def test_cli_friendly_error_on_bad_json() -> None:
    """v0.2.5 — `trugs-trl decompile <file.trl>` must give a friendly error,
    not a Python traceback. Hard to test directly (calls sys.exit); we
    verify by importing main() and capturing stderr."""
    import io
    from contextlib import redirect_stderr
    import tempfile
    # Write a non-JSON file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".trl", delete=False) as f:
        f.write("PARTY system VALIDATE.")
        path = f.name
    buf = io.StringIO()
    with redirect_stderr(buf):
        try:
            trl.main(["decompile", path])
        except SystemExit as se:
            assert se.code == 2
    assert "not valid JSON" in buf.getvalue()


# AGENT SHALL VALIDATE FUNCTION main THEN ASSERT EXCEPTION SUBJECT_TO DATA missing-file.
def test_cli_friendly_error_on_missing_file() -> None:
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = trl.main(["compile", "/nonexistent/path.trl"])
    assert rc == 2
    assert "input file not found" in buf.getvalue()


# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT DATA multiline-format SUBJECT_TO RECORD conjunction.
def test_decompile_multiline_format_for_multi_clause() -> None:
    """v0.2.5 — decompile re-breaks at conjunctions with 2-space indent."""
    src = 'PARTY api SHALL FILTER ALL ACTIVE RECORD\n  THEN SORT RESULT\n  UNLESS NO VALID RECORD REQUIRE SELF.'
    back = trl.decompile(trl.compile(src))
    # Should have line breaks before THEN and UNLESS
    assert "\n  THEN " in back
    assert "\n  UNLESS " in back


# ─── v0.3 PR-A — semantic fixes for byte-identical SPEC round-trip ────

# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT EACH RECORD mention CONTAINS DATA noun-type.
def test_per_mention_noun_type_preserved() -> None:
    """Cat D — same identifier with different noun types per mention."""
    src = (
        "PARTY user SHALL AUTHENTICATE TO SERVICE gateway.\n"
        "PARTY gateway MAY GRANT AGENT worker ON_BEHALF_OF PARTY user."
    )
    back = trl.decompile(trl.compile(src))
    assert back == src, f"got: {back!r}"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT UNIQUE RECORD anonymous-subject SUBJECT_TO DATA then-clause.
def test_anonymous_subject_inherited_without_recounter() -> None:
    """Cat C bug 1 — `EACH AGENT SHALL ... THEN MERGE ...`. The THEN clause
    inherits the same subject node, no anon-counter re-increment."""
    src = 'EACH AGENT SHALL HANDLE INPUT PARALLEL\n  THEN MERGE RESULT TO PARTY orchestrator.'
    g = trl.compile(src)
    agent_nodes = [n for n in g["nodes"] if n["type"] == "AGENT"]
    assert len(agent_nodes) == 1, f"expected 1 AGENT node, got {len(agent_nodes)}: {agent_nodes!r}"


# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT RECORD subject SUBJECT_TO DATA if-then-modal.
def test_subject_repeats_after_leading_if() -> None:
    """Cat E — first coordinated clause after IF/WHEN repeats the subject."""
    src = (
        "PARTY processor SHALL VALIDATE EACH REQUIRED RECORD.\n"
        "IF PARTY processor THROW EXCEPTION\n"
        "  THEN PARTY processor SHALL CATCH THE EXCEPTION\n"
        "  THEN HANDLE THE ERROR."
    )
    back = trl.decompile(trl.compile(src))
    assert "THEN PARTY processor SHALL CATCH" in back, f"got: {back!r}"


# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT NO RECORD subject SUBJECT_TO DATA or-same-subject.
def test_or_inherits_same_subject() -> None:
    """Cat E — OR with same subject as prior elides per SPEC #17."""
    src = (
        "WHEN PARTY client SEND MESSAGE TO SERVICE queue\n"
        "  THEN SERVICE queue SHALL VALIDATE THE MESSAGE\n"
        "  THEN SEND RESULT TO PARTY handler\n"
        "  OR REJECT THE MESSAGE."
    )
    back = trl.decompile(trl.compile(src))
    assert back == src, f"got: {back!r}"


# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT DATA adverb-after-prep IMPLEMENTS DATA line-break.
def test_adverbs_after_preps_in_decompile() -> None:
    """Cat F — adverbs come after preposition phrases in canonical form.
    PR-B refinement: when prep + adverb both present, adverb breaks to own line."""
    src = 'PARTY ingester SHALL READ EACH DATA raw-event FROM STREAM raw-events\n  WITHIN 100ms.'
    back = trl.decompile(trl.compile(src))
    # FROM is inline; WITHIN breaks to own line under prep+adverb refinement
    assert "FROM STREAM raw-events" in back
    assert "\n  WITHIN 100ms" in back, f"got: {back!r}"


# ─── v0.3 PR-B — formatting (Categories A, B, G + refinements) ──────

# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT DATA indent-depth SUBJECT_TO RECORD subordinating-conjunction.
def test_clause_depth_increases_under_subordinating_conjunction() -> None:
    """Cat A — UNLESS / PROVIDED_THAT / EXCEPT nest each clause deeper."""
    src = (
        "PARTY api SHALL FILTER ALL RECORD\n"
        "  UNLESS PARTY admin OVERRIDE\n"
        "    PROVIDED_THAT PARTY admin AUTHENTICATE TO SERVICE auth\n"
        "      EXCEPT PARTY admin ADMINISTER SERVICE auth."
    )
    g = trl.compile(src)
    back = trl.decompile(g)
    assert back == src, f"got: {back!r}"


# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT DATA structural-prep IMPLEMENTS DATA line-break.
def test_tail_structural_prep_breaks_to_new_line() -> None:
    """Cat B — SUBJECT_TO/CONTAINS after object break to new line."""
    src = (
        "PARTY administrator SHALL ADMINISTER ALL PRIVATE RESOURCE\n"
        "  CONTAINS NAMESPACE production."
    )
    back = trl.decompile(trl.compile(src))
    assert back == src, f"got: {back!r}"


# AGENT SHALL VALIDATE PROCESS compile THEN ASSERT DATA paragraph-break SUBJECT_TO RECORD round-trip.
def test_paragraph_break_preserved_through_round_trip() -> None:
    """Cat G — blank line in source survives compile/decompile."""
    src = (
        'DEFINE "word" AS DATA.\n'
        'DEFINE "constraint" AS DATA.\n'
        '\n'
        'PARTY language SHALL VALIDATE EACH DATA word.'
    )
    back = trl.decompile(trl.compile(src))
    assert back == src, f"got: {back!r}"


# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT RECORD subject SUBJECT_TO DATA modal-bearing-clause.
def test_modal_bearing_clause_repeats_subject_after_inherit() -> None:
    """Cat E refinement — modal-bearing clause always repeats subject."""
    src = (
        "PARTY processor SHALL VALIDATE EACH REQUIRED RECORD.\n"
        "IF PARTY processor THROW EXCEPTION\n"
        "  THEN PARTY processor SHALL CATCH THE EXCEPTION\n"
        "  THEN HANDLE THE ERROR\n"
        "  OR PARTY processor SHALL SEND MESSAGE TO PARTY admin."
    )
    back = trl.decompile(trl.compile(src))
    # Both modal-bearing OR/THEN clauses keep their explicit subject
    assert "OR PARTY processor SHALL SEND" in back, f"got: {back!r}"


# ─── v0.3 polish — audit follow-ups ──────────────────────────────────

# AGENT SHALL VALIDATE PROCESS decompile THEN ASSERT EXCEPTION SUBJECT_TO DATA nul-byte.
def test_decompile_rejects_nul_byte_in_graph() -> None:
    """v0.3 polish — the decompile uses `\\x00TAIL_BREAK\\x00` as an
    in-band sentinel. If a hand-built graph has `\\x00` in a node id or
    label, we'd silently swallow it. The guard refuses ambiguous output."""
    g = {
        "nodes": [
            {"id": "x\x00leak", "type": "PARTY"},
            {"id": "op-1", "type": "TRANSFORM",
             "properties": {"operation": "VALIDATE", "verb_subcategory": "obligate"}},
        ],
        "edges": [{"from_id": "x\x00leak", "to_id": "op-1", "relation": "EXECUTES"}],
    }
    try:
        trl.decompile(g)
    except trl.TRLGrammarError as e:
        assert "NUL byte" in str(e), f"unexpected error message: {e}"
        return
    raise AssertionError("expected TRLGrammarError on graph containing \\x00")


def _run_all_tests() -> int:
    """Discover and run every test_* callable in this module. Print counts.
    Exit code: 0 = all passed, 1 = at least one failed.
    """
    import sys as _sys
    import traceback as _tb
    mod = _sys.modules[__name__]
    test_names = sorted(n for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n)))
    passed: list[str] = []
    failed: list[tuple[str, str]] = []
    for name in test_names:
        try:
            getattr(mod, name)()
            passed.append(name)
        except Exception as e:
            failed.append((name, f"{type(e).__name__}: {e}"))
            _tb.print_exc(file=_sys.stderr)
    print(f"\n{len(passed)} passed, {len(failed)} failed (of {len(test_names)} total)")
    if failed:
        print("\nFailures:", file=_sys.stderr)
        for name, reason in failed:
            print(f"  {name}: {reason}", file=_sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_run_all_tests())
