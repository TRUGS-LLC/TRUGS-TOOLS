"""Tests for trugs_tools.web.hub.qualifying_interest."""

import pytest

from trugs_tools.web.hub.qualifying_interest import (
    QualifyingInterest,
    parse_qualifying_interest,
    match_interest,
    rank_matches,
    _normalise,
    _token_overlap,
)


# ============================================================================
# QualifyingInterest dataclass
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testqualifyinginterest AS A RECORD test_suite.
class TestQualifyingInterest:
    # AGENT SHALL VALIDATE PROCESS test_default_empty.
    def test_default_empty(self):
        qi = QualifyingInterest()
        assert qi.keywords == []
        assert qi.domain == ""
        assert qi.scope == ""

    # AGENT SHALL VALIDATE PROCESS test_is_valid_with_keywords.
    def test_is_valid_with_keywords(self):
        qi = QualifyingInterest(keywords=["ml"])
        assert qi.is_valid is True

    # AGENT SHALL VALIDATE PROCESS test_is_valid_empty_keywords.
    def test_is_valid_empty_keywords(self):
        qi = QualifyingInterest(keywords=[])
        assert qi.is_valid is False

    # AGENT SHALL VALIDATE PROCESS test_with_all_fields.
    def test_with_all_fields(self):
        qi = QualifyingInterest(
            keywords=["machine learning", "deep learning"],
            domain="ai",
            scope="Research on neural networks",
        )
        assert qi.keywords == ["machine learning", "deep learning"]
        assert qi.domain == "ai"
        assert qi.scope == "Research on neural networks"
        assert qi.is_valid is True


# ============================================================================
# parse_qualifying_interest
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testparsequalifyinginterest AS A RECORD test_suite.
class TestParseQualifyingInterest:
    # AGENT SHALL VALIDATE PROCESS test_dict_format.
    def test_dict_format(self):
        node = {
            "id": "root",
            "type": "RESEARCH_GRAPH",
            "properties": {
                "qualifying_interest": {
                    "keywords": ["Machine Learning", "AI"],
                    "domain": "Computer-Science",
                    "scope": "Academic research",
                }
            },
        }
        qi = parse_qualifying_interest(node)
        assert qi is not None
        assert qi.keywords == ["machine learning", "ai"]
        assert qi.domain == "computer-science"
        assert qi.scope == "Academic research"

    # AGENT SHALL VALIDATE PROCESS test_list_shorthand.
    def test_list_shorthand(self):
        node = {
            "id": "root",
            "properties": {
                "qualifying_interest": ["NLP", "Transformers"],
            },
        }
        qi = parse_qualifying_interest(node)
        assert qi is not None
        assert qi.keywords == ["nlp", "transformers"]
        assert qi.domain == ""

    # AGENT SHALL VALIDATE PROCESS test_string_shorthand.
    def test_string_shorthand(self):
        node = {
            "id": "root",
            "properties": {
                "qualifying_interest": "Biology",
            },
        }
        qi = parse_qualifying_interest(node)
        assert qi is not None
        assert qi.keywords == ["biology"]

    # AGENT SHALL VALIDATE PROCESS test_missing_qualifying_interest.
    def test_missing_qualifying_interest(self):
        node = {"id": "root", "properties": {"name": "My Graph"}}
        qi = parse_qualifying_interest(node)
        assert qi is None

    # AGENT SHALL VALIDATE PROCESS test_no_properties.
    def test_no_properties(self):
        node = {"id": "root"}
        qi = parse_qualifying_interest(node)
        assert qi is None

    # AGENT SHALL VALIDATE PROCESS test_empty_keywords.
    def test_empty_keywords(self):
        node = {
            "id": "root",
            "properties": {
                "qualifying_interest": {"keywords": []}
            },
        }
        qi = parse_qualifying_interest(node)
        assert qi is None

    # AGENT SHALL VALIDATE PROCESS test_whitespace_only_keywords.
    def test_whitespace_only_keywords(self):
        node = {
            "id": "root",
            "properties": {
                "qualifying_interest": {"keywords": ["  ", ""]}
            },
        }
        qi = parse_qualifying_interest(node)
        assert qi is None

    # AGENT SHALL VALIDATE PROCESS test_invalid_type.
    def test_invalid_type(self):
        node = {
            "id": "root",
            "properties": {"qualifying_interest": 42},
        }
        qi = parse_qualifying_interest(node)
        assert qi is None

    # AGENT SHALL VALIDATE PROCESS test_mixed_keyword_types.
    def test_mixed_keyword_types(self):
        node = {
            "id": "root",
            "properties": {
                "qualifying_interest": {"keywords": ["ai", 123, "ml"]}
            },
        }
        qi = parse_qualifying_interest(node)
        assert qi is not None
        assert "ai" in qi.keywords
        assert "123" in qi.keywords
        assert "ml" in qi.keywords


# ============================================================================
# Normalisation helpers
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testnormalise AS A RECORD test_suite.
class TestNormalise:
    # AGENT SHALL VALIDATE PROCESS test_basic.
    def test_basic(self):
        assert _normalise("Machine Learning") == "machine learning"

    # AGENT SHALL VALIDATE PROCESS test_punctuation.
    def test_punctuation(self):
        assert _normalise("C++, Python!") == "c python"

    # AGENT SHALL VALIDATE PROCESS test_whitespace.
    def test_whitespace(self):
        assert _normalise("  hello   world  ") == "hello world"


# AGENT claude SHALL DEFINE RECORD testtokenoverlap AS A RECORD test_suite.
class TestTokenOverlap:
    # AGENT SHALL VALIDATE PROCESS test_identical.
    def test_identical(self):
        assert _token_overlap({"a", "b"}, {"a", "b"}) == 1.0

    # AGENT SHALL VALIDATE PROCESS test_no_overlap.
    def test_no_overlap(self):
        assert _token_overlap({"a"}, {"b"}) == 0.0

    # AGENT SHALL VALIDATE PROCESS test_partial.
    def test_partial(self):
        # {a, b} ∩ {a, c} = {a}, union = {a, b, c}, Jaccard = 1/3
        assert abs(_token_overlap({"a", "b"}, {"a", "c"}) - 1 / 3) < 0.01

    # AGENT SHALL VALIDATE PROCESS test_empty_sets.
    def test_empty_sets(self):
        assert _token_overlap(set(), {"a"}) == 0.0
        assert _token_overlap({"a"}, set()) == 0.0
        assert _token_overlap(set(), set()) == 0.0


# ============================================================================
# match_interest
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testmatchinterest AS A RECORD test_suite.
class TestMatchInterest:
    # AGENT SHALL VALIDATE PROCESS test_identical_interests.
    def test_identical_interests(self):
        qi = QualifyingInterest(keywords=["machine learning"], domain="ai")
        score = match_interest(qi, qi)
        assert score > 0.8

    # AGENT SHALL VALIDATE PROCESS test_no_overlap.
    def test_no_overlap(self):
        a = QualifyingInterest(keywords=["biology"], domain="science")
        b = QualifyingInterest(keywords=["cooking"], domain="food")
        score = match_interest(a, b)
        assert score < 0.1

    # AGENT SHALL VALIDATE PROCESS test_partial_keyword_overlap.
    def test_partial_keyword_overlap(self):
        a = QualifyingInterest(keywords=["machine learning", "deep learning"])
        b = QualifyingInterest(keywords=["deep learning", "neural networks"])
        score = match_interest(a, b)
        assert 0.1 < score < 0.9

    # AGENT SHALL VALIDATE PROCESS test_domain_match_boost.
    def test_domain_match_boost(self):
        a = QualifyingInterest(keywords=["ml"], domain="ai")
        b_same = QualifyingInterest(keywords=["ml"], domain="ai")
        b_diff = QualifyingInterest(keywords=["ml"], domain="biology")
        score_same = match_interest(a, b_same)
        score_diff = match_interest(a, b_diff)
        assert score_same > score_diff

    # AGENT SHALL VALIDATE PROCESS test_scope_contributes.
    def test_scope_contributes(self):
        a = QualifyingInterest(
            keywords=["ml"],
            scope="research on neural architectures"
        )
        b = QualifyingInterest(
            keywords=["ml"],
            scope="research on neural architectures"
        )
        c = QualifyingInterest(
            keywords=["ml"],
            scope="cooking recipes"
        )
        score_same = match_interest(a, b)
        score_diff = match_interest(a, c)
        assert score_same > score_diff

    # AGENT SHALL VALIDATE PROCESS test_score_range.
    def test_score_range(self):
        a = QualifyingInterest(keywords=["test"])
        b = QualifyingInterest(keywords=["test"])
        score = match_interest(a, b)
        assert 0.0 <= score <= 1.0

    # AGENT SHALL VALIDATE PROCESS test_both_domains_absent.
    def test_both_domains_absent(self):
        a = QualifyingInterest(keywords=["ml"])
        b = QualifyingInterest(keywords=["ml"])
        # Both domains absent → 0.0 domain score (absence is not agreement)
        score = match_interest(a, b)
        assert score > 0.0

    # AGENT SHALL VALIDATE PROCESS test_one_domain_absent.
    def test_one_domain_absent(self):
        a = QualifyingInterest(keywords=["ml"], domain="ai")
        b = QualifyingInterest(keywords=["ml"])
        score = match_interest(a, b)
        # Domain component is 0 when one is missing
        assert score > 0.0

    # AGENT SHALL VALIDATE PROCESS test_unrelated_topics_no_floor.
    def test_unrelated_topics_no_floor(self):
        """Completely unrelated topics with no domain/scope should score 0.0."""
        a = QualifyingInterest(keywords=["quantum physics"])
        b = QualifyingInterest(keywords=["cooking recipes"])
        score = match_interest(a, b)
        assert score == 0.0


# ============================================================================
# rank_matches
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testrankmatches AS A RECORD test_suite.
class TestRankMatches:
    # AGENT SHALL VALIDATE PROCESS test_basic_ranking.
    def test_basic_ranking(self):
        interest = QualifyingInterest(keywords=["machine learning"], domain="ai")
        candidates = [
            ("ml_trug", QualifyingInterest(keywords=["machine learning"], domain="ai")),
            ("bio_trug", QualifyingInterest(keywords=["biology"], domain="science")),
            ("dl_trug", QualifyingInterest(keywords=["deep learning"], domain="ai")),
        ]
        ranked = rank_matches(interest, candidates)
        assert len(ranked) > 0
        # First result should be the exact match
        assert ranked[0][0] == "ml_trug"

    # AGENT SHALL VALIDATE PROCESS test_min_score_filter.
    def test_min_score_filter(self):
        interest = QualifyingInterest(keywords=["cooking"])
        candidates = [
            ("ml", QualifyingInterest(keywords=["machine learning"])),
        ]
        ranked = rank_matches(interest, candidates, min_score=0.5)
        assert len(ranked) == 0

    # AGENT SHALL VALIDATE PROCESS test_empty_candidates.
    def test_empty_candidates(self):
        interest = QualifyingInterest(keywords=["test"])
        ranked = rank_matches(interest, [])
        assert ranked == []

    # AGENT SHALL VALIDATE PROCESS test_results_sorted_descending.
    def test_results_sorted_descending(self):
        interest = QualifyingInterest(keywords=["python", "ml"])
        candidates = [
            ("low", QualifyingInterest(keywords=["cooking"])),
            ("high", QualifyingInterest(keywords=["python", "ml"])),
            ("mid", QualifyingInterest(keywords=["python"])),
        ]
        ranked = rank_matches(interest, candidates, min_score=0.0)
        scores = [s for _, s in ranked]
        assert scores == sorted(scores, reverse=True)
