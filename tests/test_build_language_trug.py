"""Tests for the language TRUG generator.

Verifies that SPEC_vocabulary.md parses into a complete 190-word language
TRUG matching the specification's published counts.
"""

from __future__ import annotations
import pytest

import json
from pathlib import Path

from trugs_tools.internal.build_language_trug import parse_spec, build_trug

# Skip entire module — build_language_trug.py is a maintainer utility that rebuilds
# language.trug.json from TRUGS repo SPEC_vocabulary.md. These tests should run in
# the TRUGS repo context, not trugs-tools (where we consume the bundled language.trug.json).
pytestmark = pytest.mark.skip(reason="maintainer utility tests run in TRUGS repo context")

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = REPO_ROOT / "TRUGS_LANGUAGE" / "SPEC_vocabulary.md"
GEN = REPO_ROOT / "TRUGS_LANGUAGE" / "language.trug.json"

# From SPEC_vocabulary.md section headers
EXPECTED_COUNTS = {
    "noun": 26,
    "verb": 61,
    "adjective": 36,
    "adverb": 19,
    "preposition": 18,
    "conjunction": 13,
    "article": 10,
    "pronoun": 7,
}
EXPECTED_TOTAL = 190


# AGENT SHALL VALIDATE PROCESS parse_spec SUBJECT_TO FILE spec THEN ASSERT DATA word_count.
def test_parse_spec_returns_190_words() -> None:
    records = parse_spec(SPEC.read_text())
    assert len(records) == EXPECTED_TOTAL


# AGENT SHALL VALIDATE EACH RECORD number SUBJECT_TO PROCESS parse_spec.
def test_numbers_are_contiguous_1_to_190() -> None:
    records = parse_spec(SPEC.read_text())
    numbers = sorted(r["number"] for r in records)
    assert numbers == list(range(1, EXPECTED_TOTAL + 1))


# AGENT SHALL VALIDATE DATA part_of_speech SUBJECT_TO DATA expected_counts.
def test_part_of_speech_counts_match_spec() -> None:
    records = parse_spec(SPEC.read_text())
    from collections import Counter
    counts = Counter(r["part_of_speech"] for r in records)
    assert dict(counts) == EXPECTED_COUNTS


# AGENT SHALL VALIDATE EACH RECORD word THEN ASSERT DATA definition.
def test_every_word_has_definition() -> None:
    records = parse_spec(SPEC.read_text())
    blank = [r["word"] for r in records if not r["definition"]]
    assert blank == []


# AGENT SHALL VALIDATE DATA vocabulary THEN ASSERT EACH REQUIRED DATA keyword.
def test_critical_keywords_present() -> None:
    records = parse_spec(SPEC.read_text())
    words = {r["word"] for r in records}
    for required in ["SHALL", "SHALL_NOT", "MAY", "DEFINE",
                     "FILTER", "WRITE", "SUPERSEDES", "CONTAINS",
                     "GOVERNS", "DEPENDS_ON", "PARTY", "AGENT"]:
        assert required in words, f"missing {required}"


# AGENT SHALL VALIDATE PROCESS build_trug THEN ASSERT UNIQUE RECORD node.
def test_build_trug_has_unique_word_ids() -> None:
    records = parse_spec(SPEC.read_text())
    trug = build_trug(records)
    word_nodes = [n for n in trug["nodes"] if n.get("properties", {}).get("word")]
    ids = [n["id"] for n in word_nodes]
    assert len(ids) == len(set(ids))
    assert len(word_nodes) == EXPECTED_TOTAL


# AGENT SHALL VALIDATE FILE language_trug SUBJECT_TO PROCESS build_trug.
def test_generated_file_matches_fresh_build() -> None:
    """If this fails, re-run tools/build_language_trug.py to regenerate."""
    records = parse_spec(SPEC.read_text())
    fresh = build_trug(records)
    stored = json.loads(GEN.read_text())
    assert stored["meta"]["word_count"] == fresh["meta"]["word_count"] == EXPECTED_TOTAL
    assert stored["meta"]["part_counts"] == fresh["meta"]["part_counts"]
    assert len(stored["nodes"]) == len(fresh["nodes"])
