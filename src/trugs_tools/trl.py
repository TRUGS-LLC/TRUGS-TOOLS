r"""TRL compiler — deterministic TRL ↔ TRUG round-trip.

TRL (TRUGS Language) is a closed 190-word subset of English. Every valid
sentence round-trips through a TRUG graph with no information loss beyond
sugar tokens. This module implements that round-trip.

## What's implemented

Incrementally, toward #1539 full v0.1 (round-trip all 30 canonical
examples in SPEC_examples.md):

1. **v0.1a** — minimum valid sentence: `SUBJ_NOUN id VERB .`
2. **v0.1b** — modals + single object phrase:
   `[SUBJ_NOUN id] [modal] VERB [article] [adj]* NOUN [id] .`
3. **v0.1c** — conjunctions, multi-clause sentences:
   `clause (CONJUNCTION clause)* .`
4. **v0.1d** — prepositional phrases after the verb:
   `clause := subject verb_phrase [direct_object] (PREPOSITION noun_phrase)*`
5. **v0.1e** — pronouns in object / prep-target position.
6. **v0.1f** — adverbs + value literals (INTEGER, DURATION).
7. **v0.1g** (this slice) — DEFINE / WHEREAS / STRING literals:
   - STRING literal tokens: `"quoted text"` → Token.kind="STRING"
   - `DEFINE "name" AS noun_phrase .` — emits a `DEFINED_TERM` node
     tagged with the quoted name. Per §3: `{id: name, type: NOUN,
     properties: {defined: true}}`.
   - `WHEREAS clause .` — a sentence-starting WHEREAS becomes a
     preamble. Compiles identically to a regular clause, with
     `op.properties.preamble = true` so execution semantics are
     declared as context-only.
   - Decompile restores the DEFINE / WHEREAS form verbatim.

Still not implemented: DATE literals, AND-chained prep phrases,
cross-sentence back-references (SAID), noun conjunction in
object/prep lists (e.g. `AGENT a AND AGENT b`).

## Not yet implemented (tracked in TRUGS-DEVELOPMENT#1539 / #1540)

- Modals (SHALL / MAY / SHALL_NOT)
- Articles, adjectives, adverbs
- Object phrases and prepositions
- Conjunctions (THEN / AND / OR / UNLESS / etc.)
- Pronouns (RESULT / SELF / etc.)
- Literal values (INTEGER_LITERAL / STRING_LITERAL / DURATION_LITERAL / DATE_LITERAL)
- WHEREAS preambles, DEFINE definitions

## Spec decisions for v0.1

The following are choices not fully pinned down by SPEC_grammar.md §3;
v0.1 makes them explicit so round-trip is deterministic. Will be raised
as spec-clarification issues against SPEC_grammar.md.

1. **Operation node type** — SPEC_grammar.md §3 says every VERB compiles
   to `{type: "TRANSFORM", ...}`. v0.1 follows this literally. The verb's
   actual subcategory (Obligate / Move / etc.) is preserved in
   `properties.verb_subcategory`.

2. **Unmodaled subject → operation edge** — spec §3 specifies an edge
   only when a modal is present. For unmodaled sentences, v0.1 emits
   an edge with `relation: "EXECUTES"` to keep the graph connected.
   This is a v0.1 convention, to be proposed for spec inclusion.

3. **Node IDs for identified subjects/objects** — the identifier is the
   node id (e.g. `PARTY system` → id "system"). For anonymous nouns
   (bare `RECORD` with no identifier), no node is emitted in v0.1 —
   those appear with articles/adjectives in later grammar subsets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

__all__ = [
    # Public API
    "tokenize", "parse", "compile", "decompile", "validate",
    "load_language", "classify",
    # AST types
    "Token", "NounPhrase", "VerbPhrase", "AdverbPhrase",
    "PrepPhrase", "Clause", "Sentence", "Definition",
    # Errors
    "TRLError", "TRLSyntaxError", "TRLVocabularyError", "TRLGrammarError",
    # Word-class sets (consumers may need these for spec-aware code)
    "MODALS", "CONJUNCTIONS", "PRONOUNS",
    # CLI
    "main",
]

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_LANGUAGE_TRUG = PACKAGE_ROOT / "data" / "language.trug.json"

SUGAR_RE = re.compile(r"'[a-z_]+")
IDENTIFIER_RE = re.compile(r"[a-z_][a-z0-9_-]*")
WORD_RE = re.compile(r"[A-Z_]+")
# Duration units (longest-prefix-first): ns, us, ms, s, m, h, d.
# Note `m` is treated as minutes (not meters) by convention.
DURATION_RE = re.compile(r"\d+(?:ms|us|ns|s|m|h|d)\b")
INTEGER_RE = re.compile(r"\d+")
STRING_RE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')


# ─── Tokenizer ────────────────────────────────────────────────────────

# AGENT claude SHALL DEFINE RECORD token AS A RECORD word.
@dataclass(frozen=True)
class Token:
    kind: str   # 'WORD' | 'IDENTIFIER' | 'PUNCT' | 'INTEGER' | 'DURATION' | 'STRING' | 'EOF'
    value: str
    line: int = 1     # 1-based line number in source
    col: int = 1      # 1-based column number in source

    # AGENT claude SHALL MAP RECORD token TO STRING DATA output.
    def location(self) -> str:
        """Return human-readable `line:col` for error messages."""
        return f"line {self.line}, col {self.col}"


# PROCESS tokenize SHALL SPLIT STRING DATA source THEN RETURN ALL RECORD token.
def tokenize(src: str) -> list[Token]:
    """Strip sugar, split into tokens with line/col tracking.

    Produces WORD / IDENTIFIER / PUNCT / INTEGER / DURATION / STRING.
    Whitespace is discarded. Sugar tokens (`'word`) are stripped per §1.1.

    Each token carries 1-based line and col offsets in the original source
    (BEFORE sugar stripping) so error messages can point at the actual
    location.
    """
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1

    def _advance(n: int) -> None:
        nonlocal i, line, col
        for _ in range(n):
            if i < len(src) and src[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < len(src):
        ch = src[i]
        # Sugar token — skip without emitting
        m = SUGAR_RE.match(src, i)
        if m:
            _advance(m.end() - i)
            continue
        if ch.isspace():
            _advance(1)
            continue
        tk_line, tk_col = line, col
        if ch == ".":
            tokens.append(Token("PUNCT", ".", tk_line, tk_col))
            _advance(1)
            continue
        if ch == '"':
            m = STRING_RE.match(src, i)
            if not m:
                raise TRLSyntaxError(f"unterminated string literal at line {tk_line}, col {tk_col}")
            tokens.append(Token("STRING", m.group(1), tk_line, tk_col))
            _advance(m.end() - i)
            continue
        m = WORD_RE.match(src, i)
        if m and (m.end() == len(src) or not src[m.end()].isalnum() and src[m.end()] != "_"):
            tokens.append(Token("WORD", m.group(), tk_line, tk_col))
            _advance(m.end() - i)
            continue
        m = DURATION_RE.match(src, i)
        if m:
            tokens.append(Token("DURATION", m.group(), tk_line, tk_col))
            _advance(m.end() - i)
            continue
        m = INTEGER_RE.match(src, i)
        if m:
            tokens.append(Token("INTEGER", m.group(), tk_line, tk_col))
            _advance(m.end() - i)
            continue
        m = IDENTIFIER_RE.match(src, i)
        if m:
            tokens.append(Token("IDENTIFIER", m.group(), tk_line, tk_col))
            _advance(m.end() - i)
            continue
        raise TRLSyntaxError(f"unexpected character {ch!r} at line {tk_line}, col {tk_col}")
    tokens.append(Token("EOF", "", line, col))
    return tokens


# ─── Language lookup ─────────────────────────────────────────────────

# PROCESS loader SHALL READ FILE language THEN RETURN RECORD vocabulary.
@lru_cache(maxsize=4)
def load_language(path: Optional[str] = None) -> dict:
    """Load language.trug.json, return dict of {WORD: {speech, subcategory, ...}}."""
    p = Path(path) if path else DEFAULT_LANGUAGE_TRUG
    trug = json.loads(p.read_text())
    lookup: dict[str, dict] = {}
    for node in trug["nodes"]:
        props = node.get("properties", {})
        word = props.get("word")
        if word:
            lookup[word] = {
                "speech": props.get("speech"),
                "subcategory": props.get("subcategory"),
                "definition": props.get("definition", ""),
                "core": props.get("core", False),
            }
    return lookup


# PROCESS classifier SHALL MATCH STRING DATA word SUBJECT_TO RECORD vocabulary.
def classify(word: str, lang: dict) -> dict:
    """Return {speech, subcategory, ...} for a TRUG/L word. Raises on unknown."""
    entry = lang.get(word)
    if not entry:
        raise TRLVocabularyError(f"{word!r} is not in the TRL vocabulary")
    return entry


# ─── AST ──────────────────────────────────────────────────────────────

# AGENT claude SHALL DEFINE RECORD noun_phrase AS A RECORD phrase.
@dataclass
class NounPhrase:
    noun: str = ""                  # e.g. "PARTY". Empty if pronoun is set.
    identifier: Optional[str] = None  # e.g. "system"
    article: Optional[str] = None     # "ALL" | "EACH" | "NO" | ...
    adjectives: list[str] = field(default_factory=list)  # ["PENDING", "CRITICAL"]
    pronoun: Optional[str] = None     # "RESULT" | "SELF" | "OUTPUT" | ...


# AGENT claude SHALL DEFINE RECORD adverb_phrase AS A RECORD phrase.
@dataclass
class AdverbPhrase:
    adverb: str                    # e.g. "WITHIN"
    value: Optional[str] = None    # raw literal text, e.g. "30s" or "3"


# AGENT claude SHALL DEFINE RECORD verb_phrase AS A RECORD phrase.
@dataclass
class VerbPhrase:
    verb: Optional[str] = None     # e.g. "VALIDATE"; None means inherit from prior clause
    modal: Optional[str] = None    # "SHALL" | "MAY" | "SHALL_NOT"
    adverbs: list[AdverbPhrase] = field(default_factory=list)


# AGENT claude SHALL DEFINE RECORD prep_phrase AS A RECORD phrase.
@dataclass
class PrepPhrase:
    preposition: str               # e.g. "TO"
    target: NounPhrase
    extra_targets: list[NounPhrase] = field(default_factory=list)  # AND-chained: TO a AND b AND c


# AGENT claude SHALL DEFINE RECORD clause AS A RECORD group.
@dataclass
class Clause:
    subject: Optional[NounPhrase]      # None means inherit from prior clause
    verb_phrase: VerbPhrase
    object: Optional[NounPhrase] = None
    extra_objects: list[NounPhrase] = field(default_factory=list)  # AND-chained: A AND B AND C
    prep_phrases: list["PrepPhrase"] = field(default_factory=list)
    value_arg: Optional[str] = None    # trailing INTEGER argument (e.g. "10" in TAKE RESULT 10)
    stative: bool = False              # True for `subject PREP target` clauses (no verb, no op)
    depth: int = 0                     # 0 = top-level; +1 per SUBORDINATING_CONJUNCTION nesting


# AGENT claude SHALL DEFINE RECORD definition AS A RECORD binding.
@dataclass
class Definition:
    name: str          # quoted string, e.g. "curator"
    noun_phrase: NounPhrase  # e.g. IMMUTABLE RECORD


# AGENT claude SHALL DEFINE RECORD sentence AS A RECORD statement.
@dataclass
class Sentence:
    clauses: list["Clause"] = field(default_factory=list)  # >=1 clause for normal/preamble
    conjunctions: list[str] = field(default_factory=list)  # length = len(clauses)-1
    preamble: bool = False          # True for WHEREAS preambles
    leading_conjunction: Optional[str] = None  # "IF" | "WHEN" — sentence-starting conditional
    definition: Optional[Definition] = None   # set iff this sentence is a DEFINE
    preceded_by_blank_line: bool = False  # True if source had 2+ newlines before this sentence


MODALS = {"SHALL", "MAY", "SHALL_NOT"}
CONJUNCTIONS = {
    "THEN", "AND", "OR", "ELSE", "IF", "WHEN", "WHILE", "FINALLY",
    "UNLESS", "EXCEPT", "NOTWITHSTANDING", "PROVIDED_THAT", "WHEREAS",
}
# Conjunctions where canonical form omits the subject when it matches
# the prior clause. Others always repeat the subject for clarity —
# they introduce scope or parallelism. OR inherits same-subject (SPEC
# #17 `OR REJECT THE MESSAGE`) but still requires explicit subject when
# the alternative actor differs (SPEC #3 `OR PARTY client MAY RETRY`).
INHERITING_CONJUNCTIONS = {"THEN", "FINALLY", "ELSE", "OR"}

# Subordinating conjunctions introduce a NESTED clause — depth+1 in
# canonical decompile rendering (per SPEC §2.8 + §1 examples 9, 11, 16, 25).
SUBORDINATING_CONJUNCTIONS = {
    "UNLESS", "EXCEPT", "NOTWITHSTANDING", "PROVIDED_THAT",
    "IF", "WHEN", "WHILE", "ELSE",
}
# All other CONJUNCTIONS are coordinating (same depth as parent):
# THEN, AND, OR, FINALLY, WHEREAS.

# Prepositions that get their own line in canonical decompile when they
# come after a direct object — they declare a constraint or relation on
# the result rather than being a directional complement of the verb.
# Set narrowed to only those EMPIRICALLY proven by SPEC examples to break:
#   SUBJECT_TO — #7, #12, #24, #25, #26, #28
#   CONTAINS   — #5
# The Phase 5 plan approved a wider set, but #6 disproved ON_BEHALF_OF
# (used inline) and the other "structural" preps don't appear in tail
# position with an object in the 28 examples — leave them inline by
# default; expand the set if a future SPEC example breaks on one.
STRUCTURAL_PREPOSITIONS = {"SUBJECT_TO", "CONTAINS"}
# Pronouns supported in v0.1e+ (object / prep-target positions).
# SAID and cross-sentence "THE <noun>" back-references land later.
#
# Antecedent semantics:
#   PRIOR_OP   — refers to the previous clause's op (RESULT, OUTPUT)
#   CURRENT_OP — refers to the current clause's op-self (INPUT, SOURCE, TARGET)
#   SUBJECT    — refers to the current clause's subject (SELF)
PRONOUNS_PRIOR_OP = {"RESULT", "OUTPUT"}
PRONOUNS_CURRENT_OP = {"INPUT", "SOURCE", "TARGET"}
PRONOUNS_SUBJECT_ANTECEDENT = {"SELF"}
# SAID is a "legal_reference" pronoun used article-like before a noun
# (`SAID RECORD` = "the previously-named record"). Handled in
# `_parse_noun_phrase` as a quasi-article.
PRONOUNS_LEGAL_REFERENCE = {"SAID"}
PRONOUNS = (
    PRONOUNS_PRIOR_OP | PRONOUNS_CURRENT_OP
    | PRONOUNS_SUBJECT_ANTECEDENT | PRONOUNS_LEGAL_REFERENCE
)


# ─── Errors ───────────────────────────────────────────────────────────

# AGENT claude SHALL DEFINE RECORD error AS A RECORD exception.
class TRLError(Exception):
    """Base for TRUG/L compiler errors."""


# AGENT claude SHALL DEFINE RECORD syntax_error AS A RECORD exception.
class TRLSyntaxError(TRLError):
    """Malformed TRUG/L — tokens do not match the grammar."""


# AGENT claude SHALL DEFINE RECORD vocabulary_error AS A RECORD exception.
class TRLVocabularyError(TRLError):
    """Word is not in the 190-word TRUG/L vocabulary."""


# AGENT claude SHALL DEFINE RECORD grammar_error AS A RECORD exception.
class TRLGrammarError(TRLError):
    """Valid tokens, wrong composition (e.g. modal on non-Actor subject)."""


# ─── Parser ───────────────────────────────────────────────────────────

# PROCESS parser SHALL VALIDATE ALL RECORD token THEN RETURN RECORD sentence.
def parse(src: str, lang: Optional[dict] = None) -> list[Sentence]:
    """Parse TRUG/L source into a list of Sentences.

    Detects blank lines between sentences (line gap ≥ 2) and tags the
    next sentence with `preceded_by_blank_line=True` so decompile can
    reproduce paragraph breaks (Cat G — SPEC examples #27, #28).
    """
    if lang is None:
        lang = load_language()
    tokens = tokenize(src)
    sentences: list[Sentence] = []
    pos = 0
    prev_terminator_line: Optional[int] = None

    while pos < len(tokens) and tokens[pos].kind != "EOF":
        first_line = tokens[pos].line
        sentence, pos = _parse_sentence(tokens, pos, lang)
        if prev_terminator_line is not None and first_line - prev_terminator_line >= 2:
            sentence.preceded_by_blank_line = True
        sentences.append(sentence)
        # The token before pos is the terminator '.'; record its line.
        if pos > 0 and tokens[pos - 1].kind == "PUNCT":
            prev_terminator_line = tokens[pos - 1].line

    return sentences


def _parse_noun_phrase(tokens: list[Token], pos: int, lang: dict,
                        require_identifier: bool = False,
                        allow_pronoun: bool = True) -> tuple[NounPhrase, int]:
    """Parse [article] [adjective]* NOUN [identifier], OR a bare pronoun.

    Special case: `SAID NOUN` — SAID is classified as a pronoun in the
    vocabulary but the spec uses it article-like (`SAID RECORD` = "the
    previously-named record"). When SAID is followed by a noun token,
    parse as `article=SAID + noun`.
    """
    # Pronoun shortcut (object / prep-target position).
    if tokens[pos].kind == "WORD" and tokens[pos].value in PRONOUNS:
        # SAID-as-article-like check
        if tokens[pos].value == "SAID" and pos + 1 < len(tokens):
            nxt = tokens[pos + 1]
            if nxt.kind == "WORD":
                e = lang.get(nxt.value)
                if e and e["speech"] == "noun":
                    # Treat SAID as an article quantifier; fall through to normal
                    # noun_phrase parsing below.
                    article_override = "SAID"
                    pos += 1
                    article: Optional[str] = article_override
                    adjectives: list[str] = []
                    # Required noun
                    noun_tok = tokens[pos]
                    noun = noun_tok.value
                    pos += 1
                    # Optional identifier
                    identifier: Optional[str] = None
                    if pos < len(tokens) and tokens[pos].kind == "IDENTIFIER":
                        identifier = tokens[pos].value
                        pos += 1
                    return NounPhrase(noun=noun, identifier=identifier,
                                      article=article, adjectives=adjectives), pos

        if not allow_pronoun:
            raise TRLGrammarError(
                f"{tokens[pos].value!r} is a pronoun and cannot appear here — subjects require a noun phrase"
            )
        if require_identifier:
            raise TRLGrammarError(
                f"{tokens[pos].value!r} is a pronoun and cannot be a required-identifier subject"
            )
        pronoun_word = tokens[pos].value
        return NounPhrase(pronoun=pronoun_word), pos + 1

    article: Optional[str] = None
    adjectives: list[str] = []

    # Optional article
    if tokens[pos].kind == "WORD":
        entry = lang.get(tokens[pos].value)
        if entry and entry["speech"] == "article":
            article = tokens[pos].value
            pos += 1

    # Article + pronoun shortcut (e.g. EACH RESULT)
    if article is not None and tokens[pos].kind == "WORD" and tokens[pos].value in PRONOUNS:
        if not allow_pronoun:
            raise TRLGrammarError(f"{tokens[pos].value!r} pronoun not allowed here")
        np = NounPhrase(article=article, pronoun=tokens[pos].value)
        return np, pos + 1

    # Zero or more adjectives
    while tokens[pos].kind == "WORD":
        entry = lang.get(tokens[pos].value)
        if entry and entry["speech"] == "adjective":
            adjectives.append(tokens[pos].value)
            pos += 1
        else:
            break

    # Required noun
    if tokens[pos].kind != "WORD":
        raise TRLSyntaxError(
            f"expected noun at {tokens[pos].location()}, got {tokens[pos].kind} {tokens[pos].value!r}"
        )
    noun = tokens[pos].value
    entry = classify(noun, lang)
    if entry["speech"] != "noun":
        raise TRLGrammarError(f"{noun!r} is a {entry['speech']}, not a noun")
    pos += 1

    # Optional identifier
    identifier: Optional[str] = None
    if tokens[pos].kind == "IDENTIFIER":
        identifier = tokens[pos].value
        pos += 1
    elif require_identifier:
        raise TRLGrammarError(f"{noun!r} requires an identifier as a subject")

    return NounPhrase(noun=noun, identifier=identifier, article=article, adjectives=adjectives), pos


def _peek_and_noun_phrase(tokens: list[Token], pos: int, lang: dict) -> bool:
    """True if the current token is AND introducing a noun_list extension.

    Disambiguates noun_list AND (binds within prep_phrase / object list) from
    clause-level AND (joins clauses with verbs). Algorithm: speculatively parse
    a noun_phrase after the AND; if what follows that noun_phrase is a modal
    or verb, the AND is clause-level (the noun_phrase is the next clause's
    subject). Otherwise it's noun_list AND.
    """
    if pos >= len(tokens) or tokens[pos].kind != "WORD" or tokens[pos].value != "AND":
        return False
    nxt = tokens[pos + 1] if pos + 1 < len(tokens) else None
    if nxt is None or nxt.kind != "WORD":
        return False
    if nxt.value in MODALS or nxt.value in CONJUNCTIONS:
        return False
    e = lang.get(nxt.value)
    if not e or e["speech"] not in ("noun", "article", "adjective", "pronoun"):
        return False
    # Speculatively parse the noun_phrase starting at pos+1; check the
    # follow-on token. If modal/verb, it's clause-level AND.
    try:
        _, after = _parse_noun_phrase(tokens, pos + 1, lang, require_identifier=False)
    except TRLError:
        return False
    follow = tokens[after] if after < len(tokens) else None
    if follow is not None and follow.kind == "WORD":
        if follow.value in MODALS:
            return False
        f_entry = lang.get(follow.value)
        if f_entry and f_entry["speech"] == "verb":
            return False
    return True


def _parse_clause(tokens: list[Token], pos: int, lang: dict,
                   require_subject: bool) -> tuple[Clause, int]:
    """Parse one clause: [subject] [modal] VERB [object].

    Clause terminates when the next token is '.', EOF, or a CONJUNCTION.
    """
    subject: Optional[NounPhrase] = None
    if require_subject:
        # First clause — subject required but identifier optional.
        # Anonymous subjects like "ALL RECORD" or "NO PARTY" are valid
        # per SPEC_grammar.md §1 BNF (noun_phrase := [ARTICLE] [ADJ]* NOUN [id]).
        # Pronouns as subjects are deferred past v0.1.
        subject, pos = _parse_noun_phrase(tokens, pos, lang, require_identifier=False, allow_pronoun=False)
    else:
        # Speculative parse: try noun_phrase, check that modal/verb follows.
        # If it doesn't, back up and inherit subject from prior clause.
        saved_pos = pos
        cur = tokens[pos]
        if cur.kind == "WORD" and lang.get(cur.value, {}).get("speech") in ("noun", "article", "adjective"):
            try:
                trial_subject, trial_pos = _parse_noun_phrase(tokens, pos, lang, require_identifier=False)
                # Commit subject if the next token is:
                #   - a modal or verb (regular clause)
                #   - a preposition (stative clause: subject + PREP + target)
                #   - a CONJUNCTION (subject-only with elided verb, joined to next clause)
                #   - PUNCT '.' (subject-only carve-out, verb elided)
                nxt = tokens[trial_pos]
                if (nxt.kind == "PUNCT" and nxt.value == ".") or (nxt.kind == "WORD" and (
                    nxt.value in MODALS
                    or nxt.value in CONJUNCTIONS
                    or lang.get(nxt.value, {}).get("speech") in ("verb", "preposition")
                )):
                    subject = trial_subject
                    pos = trial_pos
            except TRLError:
                pos = saved_pos

    # Optional modal
    modal: Optional[str] = None
    if tokens[pos].kind == "WORD" and tokens[pos].value in MODALS:
        modal = tokens[pos].value
        pos += 1

    # Verb. May be elided when the clause is a subject-only carve-out (e.g.
    # `EXCEPT PARTY system` after a clause that established the verb).
    # Returns verb=None to signal verb-inheritance to the caller.
    verb: Optional[str] = None
    if tokens[pos].kind == "WORD":
        v = tokens[pos].value
        v_entry = lang.get(v)
        if v_entry and v_entry["speech"] == "verb" and v not in MODALS:
            verb = v
            pos += 1
        elif tokens[pos].kind == "PUNCT" or v in CONJUNCTIONS:
            pass  # subject-only clause, verb inherited
    # If we still don't have a verb and the next token isn't a sentence
    # terminator or another conjunction, fall through — caller may treat
    # as stative or error.
    if verb is None and tokens[pos].kind != "PUNCT" and not (
        tokens[pos].kind == "WORD" and tokens[pos].value in CONJUNCTIONS
    ):
        # Allow stative form: subject + PREPOSITION + noun_phrase
        # (handled below — verb stays None and we fall through to the
        # post-verb loop, which will pick up the preposition).
        pass

    # After the verb: a mix of adverbs, one optional direct object, and zero or
    # more prep phrases, in any source order. Accept until punctuation/conjunction.
    adverbs: list[AdverbPhrase] = []
    obj: Optional[NounPhrase] = None
    extra_objects: list[NounPhrase] = []
    prep_phrases: list[PrepPhrase] = []
    value_arg: Optional[str] = None

    while tokens[pos].kind != "PUNCT" and tokens[pos].kind != "EOF":
        # Trailing INTEGER as a verb-argument (e.g. TAKE RESULT 10, BATCH RESULT 100)
        if tokens[pos].kind == "INTEGER":
            if value_arg is not None:
                break  # only one trailing int per verb
            value_arg = tokens[pos].value
            pos += 1
            continue
        if tokens[pos].kind != "WORD":
            break
        if tokens[pos].value in CONJUNCTIONS:
            break
        tok = tokens[pos]
        entry = lang.get(tok.value)
        if not entry:
            break
        sp = entry["speech"]
        if sp == "adverb":
            adv_word = tok.value
            pos += 1
            adv_value: Optional[str] = None
            if tokens[pos].kind in ("DURATION", "INTEGER"):
                adv_value = tokens[pos].value
                pos += 1
            adverbs.append(AdverbPhrase(adverb=adv_word, value=adv_value))
        elif sp == "preposition":
            prep_word = tok.value
            pos += 1
            target, pos = _parse_noun_phrase(tokens, pos, lang, require_identifier=False)
            extras: list[NounPhrase] = []
            # AND-chained noun_list within a prep_phrase: TO a AND b AND c
            while _peek_and_noun_phrase(tokens, pos, lang):
                pos += 1  # consume AND
                extra, pos = _parse_noun_phrase(tokens, pos, lang, require_identifier=False)
                extras.append(extra)
            prep_phrases.append(PrepPhrase(preposition=prep_word, target=target, extra_targets=extras))
        elif sp in ("noun", "article", "adjective", "pronoun") and obj is None:
            obj, pos = _parse_noun_phrase(tokens, pos, lang, require_identifier=False)
            # AND-chained object list: MERGE A AND B AND C
            while _peek_and_noun_phrase(tokens, pos, lang):
                pos += 1  # consume AND
                extra, pos = _parse_noun_phrase(tokens, pos, lang, require_identifier=False)
                extra_objects.append(extra)
        else:
            break

    # Detect stative clause: no verb, no modal, no object, only prep_phrases.
    # Example: `THE REMEDY DEPENDS_ON PARTY owner.`
    stative = (
        verb is None
        and modal is None
        and obj is None
        and not adverbs
        and len(prep_phrases) >= 1
    )

    return Clause(
        subject=subject,
        verb_phrase=VerbPhrase(verb=verb, modal=modal, adverbs=adverbs),
        object=obj,
        extra_objects=extra_objects,
        prep_phrases=prep_phrases,
        value_arg=value_arg,
        stative=stative,
    ), pos


def _parse_definition(tokens: list[Token], pos: int, lang: dict) -> tuple[Sentence, int]:
    """Parse `DEFINE "name" AS noun_phrase .`. Caller has NOT consumed DEFINE yet."""
    assert tokens[pos].kind == "WORD" and tokens[pos].value == "DEFINE"
    pos += 1
    if tokens[pos].kind != "STRING":
        raise TRLSyntaxError(f"DEFINE requires a quoted string name, got {tokens[pos]!r}")
    name = tokens[pos].value
    pos += 1
    if tokens[pos].kind != "WORD" or tokens[pos].value != "AS":
        raise TRLSyntaxError(f"expected 'AS' after DEFINE name, got {tokens[pos]!r}")
    pos += 1
    np, pos = _parse_noun_phrase(tokens, pos, lang, require_identifier=False)
    if tokens[pos].kind != "PUNCT" or tokens[pos].value != ".":
        raise TRLSyntaxError(f"expected '.' after DEFINE clause, got {tokens[pos]!r}")
    pos += 1
    return Sentence(definition=Definition(name=name, noun_phrase=np)), pos


def _parse_sentence(tokens: list[Token], pos: int, lang: dict) -> tuple[Sentence, int]:
    # DEFINE definition — sentence-level
    if tokens[pos].kind == "WORD" and tokens[pos].value == "DEFINE":
        return _parse_definition(tokens, pos, lang)

    # Sentence-starting prefixes: WHEREAS preamble or IF/WHEN conditional.
    # Each tags the first clause's op with a property so decompile reproduces it.
    preamble = False
    leading_conjunction: Optional[str] = None
    if tokens[pos].kind == "WORD":
        if tokens[pos].value == "WHEREAS":
            preamble = True
            pos += 1
        elif tokens[pos].value in ("IF", "WHEN"):
            leading_conjunction = tokens[pos].value
            pos += 1

    clauses: list[Clause] = []
    conjunctions: list[str] = []

    # First clause — subject required
    clause, pos = _parse_clause(tokens, pos, lang, require_subject=True)
    clause.depth = 0
    clauses.append(clause)

    # Subsequent clauses joined by conjunctions. Track depth: each
    # SUBORDINATING_CONJUNCTION nests under its parent (depth+1);
    # COORDINATING conjunctions stay at the parent's depth.
    current_depth = 0
    while tokens[pos].kind == "WORD" and tokens[pos].value in CONJUNCTIONS:
        conj = tokens[pos].value
        pos += 1
        clause, pos = _parse_clause(tokens, pos, lang, require_subject=False)
        if conj in SUBORDINATING_CONJUNCTIONS:
            current_depth += 1
        clause.depth = current_depth
        clauses.append(clause)
        conjunctions.append(conj)

    # Terminator
    if tokens[pos].kind != "PUNCT" or tokens[pos].value != ".":
        raise TRLSyntaxError(
            f"expected '.' at {tokens[pos].location()}, got {tokens[pos].kind} {tokens[pos].value!r}. "
            "Check that the previous clause is well-formed (subject + verb + objects)."
        )
    pos += 1

    return Sentence(
        clauses=clauses, conjunctions=conjunctions, preamble=preamble,
        leading_conjunction=leading_conjunction,
    ), pos


# ─── Compile (TRUG/L → TRUG) ─────────────────────────────────────────

# PROCESS compiler SHALL MAP STRING DATA source TO RECORD graph.
def compile(src_or_sentences, lang: Optional[dict] = None) -> dict:
    """Compile TRUG/L into a TRUG graph fragment (nodes + edges).

    Accepts a string or a pre-parsed list[Sentence]. Returns a graph
    dict with keys {nodes, edges}. Deterministic — the same input
    always produces the same graph.
    """
    if lang is None:
        lang = load_language()
    sentences = parse(src_or_sentences, lang) if isinstance(src_or_sentences, str) else src_or_sentences

    nodes: list[dict] = []
    edges: list[dict] = []
    op_counter = 0
    anon_counters: dict[str, int] = {}

    def _np_shape(np: NounPhrase) -> dict:
        """Per-mention attributes (noun type, article, adjectives) grouped by subcategory.

        `noun_type` is the noun word at this mention. Different mentions of
        the same identified entity may use different noun types (e.g.
        `PARTY gateway` and `SERVICE gateway` both refer to the entity
        `gateway`); the node carries one fallback type, but each mention's
        actual rendering uses the per-edge `noun_type` from this shape.
        """
        shape: dict = {}
        if np.noun:
            shape["noun_type"] = np.noun
        if np.article:
            shape["article"] = np.article
        if np.adjectives:
            adj_groups: dict[str, list[str]] = {}
            for adj in np.adjectives:
                sub = classify(adj, lang)["subcategory"]
                adj_groups.setdefault(sub, []).append(adj)
            for sub, vals in adj_groups.items():
                shape[sub] = vals[0] if len(vals) == 1 else vals
        return shape

    def _ensure_noun_node(np: NounPhrase) -> str:
        """Emit (or reuse) a node for a noun_phrase, return its id.

        The node carries only `id` and `type`. Per-mention attributes
        (article, adjectives) live on the EDGE that references the node,
        so different mentions can have different shapes (e.g. one
        sentence references `RECORD ledger` and another `THE RECORD ledger`).
        """
        if np.identifier:
            node_id = np.identifier
        else:
            anon_counters[np.noun] = anon_counters.get(np.noun, 0) + 1
            node_id = f"{np.noun.lower()}-{anon_counters[np.noun]}"
        if not any(n["id"] == node_id for n in nodes):
            nodes.append({"id": node_id, "type": np.noun})
        return node_id

    inherited_verb_phrase: Optional[VerbPhrase] = None
    cross_sentence_prev_op: Optional[str] = None

    def _mark_first_node_for_sentence(sentence: Sentence, before_index: int,
                                       first_op_id: Optional[str] = None) -> None:
        """Tag the first emit-target node for this sentence so decompile
        can emit a blank line. For DEFINE sentences we tag the DEFINED_TERM
        node; for operative sentences we tag the first OP node (which
        anchors the sentence walk)."""
        if not sentence.preceded_by_blank_line:
            return
        target: Optional[dict] = None
        if first_op_id is not None:
            target = next((n for n in nodes if n["id"] == first_op_id), None)
        if target is None and before_index < len(nodes):
            target = nodes[before_index]
        if target is not None:
            target.setdefault("properties", {})["preceded_by_blank_line"] = True

    for sentence in sentences:
        _node_count_before = len(nodes)
        # DEFINE sentence: emit a DEFINED_TERM node, no ops/edges.
        # DEFINE-site attributes (article + adjectives) live under
        # `properties.defined_attributes` so they only render at the
        # DEFINE site and don't leak into later references to the term.
        if sentence.definition is not None:
            d = sentence.definition
            def_props: dict = {"defined": True, "name": d.name}
            attrs: dict = {}
            if d.noun_phrase.article:
                attrs["article"] = d.noun_phrase.article
            for adj in d.noun_phrase.adjectives:
                sub = classify(adj, lang)["subcategory"]
                attrs.setdefault(sub, adj)
            if attrs:
                def_props["defined_attributes"] = attrs
            nodes.append({
                "id": d.name,
                "type": d.noun_phrase.noun,
                "properties": def_props,
            })
            continue

        inherited_subject: Optional[NounPhrase] = None
        clause_op_ids: list[str] = []
        # Inherit prev_op from the prior sentence so cross-sentence
        # RESULT/OUTPUT pronouns can resolve.
        prev_op_id: Optional[str] = cross_sentence_prev_op

        def _resolve_pronoun(np: NounPhrase, current_subj_id: str, current_op_id: str) -> str:
            """Return the antecedent node id for a pronoun noun_phrase."""
            word = np.pronoun
            if word in PRONOUNS_SUBJECT_ANTECEDENT:
                return current_subj_id
            if word in PRONOUNS_CURRENT_OP:
                return current_op_id
            if word in PRONOUNS_PRIOR_OP:
                if prev_op_id is None:
                    raise TRLGrammarError(
                        f"pronoun {word!r} has no prior clause to reference"
                    )
                return prev_op_id
            raise TRLGrammarError(f"unhandled pronoun {word!r}")

        last_subject_id: Optional[str] = None  # for inheriting anon subjects without re-counter
        last_subject_shape: Optional[dict] = None
        for clause in sentence.clauses:
            if clause.subject is not None:
                subject_np = clause.subject
                subj_id = _ensure_noun_node(subject_np)
                last_subject_shape = _np_shape(subject_np)
                inherited_subject = subject_np
            else:
                # Inherit subject node + shape from prior clause's emission
                if last_subject_id is None:
                    if inherited_subject is None:
                        raise TRLGrammarError(
                            "clause has no subject and no prior clause to inherit from"
                        )
                    subject_np = inherited_subject
                    subj_id = _ensure_noun_node(subject_np)
                    last_subject_shape = _np_shape(subject_np)
                else:
                    subj_id = last_subject_id
                    subject_np = inherited_subject  # for pronoun-resolution below
            last_subject_id = subj_id

            # Stative clause: no op, just direct edges subject → target via PREP.
            if clause.stative:
                # Subject's shape goes on the FIRST stative edge (subjects don't
                # have their own edge in stative form).
                subj_shape = _np_shape(subject_np)
                for i, pp in enumerate(clause.prep_phrases):
                    target_id = _ensure_noun_node(pp.target)
                    e_props: dict = {}
                    if sentence.preamble:
                        e_props["preamble"] = True
                    if i == 0 and subj_shape:
                        e_props["subject_np_shape"] = subj_shape
                    target_shape = _np_shape(pp.target)
                    if target_shape:
                        e_props["np_shape"] = target_shape
                    edge: dict = {"from_id": subj_id, "to_id": target_id, "relation": pp.preposition}
                    if e_props:
                        edge["properties"] = e_props
                    edges.append(edge)
                # Use the stative subject id as the "op id slot" so any
                # following conjunction edge has a target. The conjunction
                # edge ends up pointing at the stative subject, which the
                # decompiler interprets as "THEN <stative clause>".
                clause_op_ids.append(subj_id)
                # Don't update prev_op_id (pronouns shouldn't reference statives)
                continue

            # Verb may be elided in carve-out clauses (e.g. EXCEPT PARTY system).
            # Inherit verb_phrase from prior clause if so.
            effective_vp = clause.verb_phrase
            if effective_vp.verb is None:
                if inherited_verb_phrase is None:
                    raise TRLGrammarError(
                        "clause has no verb and no prior clause to inherit from"
                    )
                # Keep clause's own modal if present, otherwise inherit prior modal too
                effective_vp = VerbPhrase(
                    verb=inherited_verb_phrase.verb,
                    modal=clause.verb_phrase.modal or inherited_verb_phrase.modal,
                    adverbs=clause.verb_phrase.adverbs,
                )
            inherited_verb_phrase = effective_vp

            op_counter += 1
            op_id = f"op-{op_counter}"
            op_props: dict = {
                "operation": effective_vp.verb,
                "verb_subcategory": classify(effective_vp.verb, lang)["subcategory"],
            }
            if effective_vp.adverbs:
                op_props["adverbs"] = [
                    ({"adverb": a.adverb, "value": a.value}
                     if a.value is not None else {"adverb": a.adverb})
                    for a in effective_vp.adverbs
                ]
            if sentence.preamble and not clause_op_ids:
                op_props["preamble"] = True
            if sentence.leading_conjunction and not clause_op_ids:
                op_props["leading_conjunction"] = sentence.leading_conjunction
            if clause.value_arg is not None:
                op_props["value_arg"] = clause.value_arg
            if clause.verb_phrase.verb is None:
                # Original source had no verb — mark for elision on decompile
                op_props["verb_elided"] = True
            if clause.depth:
                op_props["depth"] = clause.depth
            nodes.append({"id": op_id, "type": "TRANSFORM", "properties": op_props})

            relation = effective_vp.modal if effective_vp.modal else "EXECUTES"
            subj_edge: dict = {"from_id": subj_id, "to_id": op_id, "relation": relation}
            subj_shape = _np_shape(subject_np)
            if subj_shape:
                subj_edge["properties"] = {"np_shape": subj_shape}
            edges.append(subj_edge)

            chain_counter = 0

            def _emit_target_edge(np: NounPhrase, relation: str, chain_id: Optional[int]) -> None:
                edge_props: dict = {}
                if np.pronoun:
                    target_id = _resolve_pronoun(np, subj_id, op_id)
                    edge_props["pronoun"] = np.pronoun
                    # Article-before-pronoun (e.g. EACH RESULT) — store article
                    # alongside the pronoun so decompile can reproduce it.
                    if np.article:
                        edge_props["pronoun_article"] = np.article
                else:
                    target_id = _ensure_noun_node(np)
                    shape = _np_shape(np)
                    if shape:
                        edge_props["np_shape"] = shape
                if chain_id is not None:
                    edge_props["chain_id"] = chain_id
                edge: dict = {"from_id": op_id, "to_id": target_id, "relation": relation}
                if edge_props:
                    edge["properties"] = edge_props
                edges.append(edge)

            if clause.object is not None:
                cid: Optional[int] = None
                if clause.extra_objects:
                    chain_counter += 1
                    cid = chain_counter
                _emit_target_edge(clause.object, "ACTS_ON", cid)
                for extra in clause.extra_objects:
                    _emit_target_edge(extra, "ACTS_ON", cid)

            for pp in clause.prep_phrases:
                cid = None
                if pp.extra_targets:
                    chain_counter += 1
                    cid = chain_counter
                _emit_target_edge(pp.target, pp.preposition, cid)
                for extra in pp.extra_targets:
                    _emit_target_edge(extra, pp.preposition, cid)

            clause_op_ids.append(op_id)
            prev_op_id = op_id
            cross_sentence_prev_op = op_id

        # Conjunction edges between consecutive ops in the same sentence
        for i, conj in enumerate(sentence.conjunctions):
            edges.append({
                "from_id": clause_op_ids[i],
                "to_id": clause_op_ids[i + 1],
                "relation": conj,
            })

        # Mark the FIRST node emitted during this sentence with the
        # preceded_by_blank_line flag (Cat G — paragraph break). For
        # operative sentences we tag the first op (anchors decompile walk).
        first_op = clause_op_ids[0] if clause_op_ids else None
        _mark_first_node_for_sentence(sentence, _node_count_before, first_op_id=first_op)

    return {"nodes": nodes, "edges": edges}


# ─── Decompile (TRUG → TRL) ───────────────────────────────────────────

def _is_anonymous_id(node: dict, mention_type: Optional[str] = None) -> bool:
    """Auto-generated IDs follow `{type_lower}-N`. Skip them on render.

    `mention_type` is the per-mention noun type from the edge shape; when
    a node is referenced via a different type than its node["type"], the
    auto-id pattern is anchored on the node's first-mention type, so we
    check against that.
    """
    base = (mention_type or node["type"]).lower()
    if re.fullmatch(rf"{re.escape(base)}-\d+", node["id"]) is not None:
        return True
    # Also catch the case where node["type"] differs from mention_type
    return re.fullmatch(rf"{re.escape(node['type'].lower())}-\d+", node["id"]) is not None


def _render_noun_phrase(node: dict, lang: dict, shape: Optional[dict] = None) -> str:
    """Render a noun node back to its TRL form: [article] [adj]* NOUN [id].

    `shape` is per-mention attributes (noun_type + article + adjectives)
    carried on the edge that references the node. The noun TYPE used in
    rendering comes from `shape['noun_type']` if present, otherwise from
    the node's own `type` (the first-mention fallback).
    """
    parts: list[str] = []
    shape = shape or {}
    article = shape.get("article")
    if article:
        parts.append(article)

    # Adjectives: reconstruct in §2.5 fixed order
    adj_order = ["quantity", "priority", "state", "access", "type"]
    for sub in adj_order:
        vals = shape.get(sub)
        if vals is None:
            continue
        if sub == "type" and isinstance(vals, str) and vals.isupper() and not lang.get(vals, {}).get("speech") == "adjective":
            continue
        if isinstance(vals, str):
            parts.append(vals)
        elif isinstance(vals, list):
            parts.extend(vals)

    noun_type = shape.get("noun_type") or node["type"]
    parts.append(noun_type)
    if not _is_anonymous_id(node, noun_type):
        parts.append(node["id"])
    return " ".join(parts)


def _render_clause(op_id: str, op_nodes: dict, edges: list[dict], nodes_by_id: dict,
                    lang: dict, include_subject: bool) -> str:
    """Render a single clause (subject + modal + verb + object)."""
    op = op_nodes[op_id]
    # Find subject edge (modal or EXECUTES incoming)
    subj_edge = next((e for e in edges if e["to_id"] == op_id
                      and e.get("relation") in MODALS | {"EXECUTES"}), None)
    if subj_edge is None:
        raise TRLGrammarError(f"op {op_id} has no subject edge")
    subj_node = nodes_by_id[subj_edge["from_id"]]
    modal = subj_edge.get("relation")

    parts: list[str] = []
    if include_subject:
        subj_shape = (subj_edge.get("properties") or {}).get("np_shape")
        parts.append(_render_noun_phrase(subj_node, lang=lang, shape=subj_shape))
    elided = op["properties"].get("verb_elided")
    if modal in MODALS and not elided:
        parts.append(modal)
    elif modal != "EXECUTES" and modal not in MODALS:
        raise TRLGrammarError(f"unknown subject→operation relation {modal!r}")
    if not elided:
        parts.append(op["properties"]["operation"])

    preposition_words = {w for w, e in lang.items() if e["speech"] == "preposition"}

    # Canonical post-verb order:
    #   1. direct object (ACTS_ON edge, if any)
    #   2. preposition phrases (outgoing preposition edges, in edge-list order)
    #   3. adverbs (op.properties.adverbs, in stored order)
    #   4. trailing integer argument (TAKE RESULT 10, BATCH RESULT 100)
    # SPEC_examples.md examples #7/#15/#18 have no preps + adverbs after
    # object — handled. Example #28 has both, with adverbs after preps —
    # handled by this order.

    def _render_target(e: dict) -> str:
        props = e.get("properties") or {}
        pronoun = props.get("pronoun")
        if pronoun:
            article = props.get("pronoun_article")
            return f"{article} {pronoun}" if article else pronoun
        node = nodes_by_id.get(e["to_id"])
        if node is None:
            return ""
        shape = props.get("np_shape")
        return _render_noun_phrase(node, lang=lang, shape=shape)

    # 1. Direct object(s) — possibly AND-chained via chain_id.
    # AND-chains stay inline. SPEC examples disagree on when to break
    # before AND in object lists (#23 keeps `MODULE a AND MODULE b AND
    # MODULE c` inline; #27 breaks similar list; #20 breaks complex
    # object-with-prep groups). The pattern is too stylistic for a
    # deterministic rule — leave inline as the canonical form. SPEC may
    # be updated to match (or this rule refined when a clear signal emerges).
    obj_edges = [e for e in edges
                 if e["from_id"] == op_id and e.get("relation") == "ACTS_ON"]
    if obj_edges:
        first = obj_edges[0]
        parts.append(_render_target(first))
        cid = (first.get("properties") or {}).get("chain_id")
        if cid is not None:
            for e in obj_edges[1:]:
                if (e.get("properties") or {}).get("chain_id") == cid:
                    parts.append("AND")
                    parts.append(_render_target(e))

    # 2. Preposition phrases — group AND-chained noun_lists by chain_id.
    # Structural prepositions (SUBJECT_TO, CONTAINS, ...) get a sentinel
    # `\x00TAIL_BREAK\x00` inserted before them; sentence-assembly
    # replaces the sentinel with `\n` + parent-indent + 2 spaces.
    rendered_chain_ids: set[int] = set()
    has_object = bool(obj_edges)
    for e in edges:
        if e["from_id"] != op_id:
            continue
        rel = e.get("relation")
        if rel not in preposition_words:
            continue
        cid = (e.get("properties") or {}).get("chain_id")
        if cid is not None and cid in rendered_chain_ids:
            continue
        # Tail-prep break: structural prep AFTER an object goes on its own line
        if rel in STRUCTURAL_PREPOSITIONS and has_object:
            parts.append("\x00TAIL_BREAK\x00")
        parts.append(rel)
        parts.append(_render_target(e))
        if cid is not None:
            rendered_chain_ids.add(cid)
            for e2 in edges:
                if (e2["from_id"] == op_id
                        and e2.get("relation") == rel
                        and (e2.get("properties") or {}).get("chain_id") == cid
                        and e2 is not e):
                    parts.append("AND")
                    parts.append(_render_target(e2))

    # 3. Adverbs (after preps so #28's `... FROM STREAM raw-events WITHIN 100ms` round-trips).
    # When the clause has prep phrases AND adverbs, the SPEC convention
    # breaks before each adverb (Cat F refinement, #28). When there are no
    # prep phrases, adverbs stay inline (#3, #15, #18).
    has_preps = any(
        e.get("relation") in preposition_words
        for e in edges if e["from_id"] == op_id
    )
    advs = op["properties"].get("adverbs", [])
    for adv in advs:
        if has_preps and advs:
            parts.append("\x00TAIL_BREAK\x00")
        parts.append(adv["adverb"])
        if "value" in adv and adv["value"] is not None:
            parts.append(adv["value"])

    # 4. Trailing integer argument (TAKE RESULT 10, BATCH RESULT 100)
    if op["properties"].get("value_arg") is not None:
        parts.append(op["properties"]["value_arg"])

    return " ".join(parts)


def _render_define(node: dict, lang: dict) -> str:
    """Render a DEFINED_TERM node back to its `DEFINE "name" AS np .` form."""
    props = node.get("properties") or {}
    attrs = props.get("defined_attributes") or {}
    name = props.get("name", node["id"])
    parts = [f'DEFINE "{name}" AS']
    article = attrs.get("article")
    if article:
        parts.append(article)
    for sub in ["quantity", "priority", "state", "access", "type"]:
        val = attrs.get(sub)
        if val is None:
            continue
        if sub == "type" and isinstance(val, str) and val.isupper() \
                and not lang.get(val, {}).get("speech") == "adjective":
            continue
        if isinstance(val, str):
            parts.append(val)
    parts.append(node["type"])
    return " ".join(parts) + "."


# PROCESS decompiler SHALL MAP RECORD graph TO STRING DATA source.
def decompile(graph: dict, lang: Optional[dict] = None) -> str:
    """Turn a TRUG graph fragment back into canonical TRUG/L source."""
    if lang is None:
        lang = load_language()

    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    op_nodes = {n["id"]: n for n in graph["nodes"]
                if n.get("type") == "TRANSFORM"
                and n.get("properties", {}).get("operation")}
    edges = graph["edges"]

    # Index conjunction edges: op_from -> (conjunction_word, target_id).
    # Target may be an op (regular conjunction) or a non-op subject node
    # (stative continuation: ... THEN <stative-clause>).
    conj_next: dict[str, tuple[str, str]] = {}
    conj_targets: set[str] = set()
    for e in edges:
        rel = e.get("relation")
        if rel in CONJUNCTIONS and e["from_id"] in op_nodes:
            conj_next[e["from_id"]] = (rel, e["to_id"])
            conj_targets.add(e["to_id"])

    preposition_words_set = {w for w, ent in lang.items() if ent["speech"] == "preposition"}
    # Stative edges: source is NOT an op-node, relation is a preposition.
    # Emit one stative sentence per such edge, in graph edge order.
    stative_edges: list[dict] = [
        e for e in edges
        if e["from_id"] not in op_nodes
        and e.get("relation") in preposition_words_set
    ]
    rendered_stative: set[int] = set()  # by edge index

    sentences_out: list[str] = []
    visited_ops: set[str] = set()

    # Track which graph element we should emit next, by walking nodes + edges
    # in source order. Stative edges are interleaved with op-rooted sentences
    # using a simple heuristic: emit stative for any edge whose target node
    # appears in the graph before the next op.
    def _emit_stative(e: dict) -> str:
        subj = nodes_by_id.get(e["from_id"])
        tgt = nodes_by_id.get(e["to_id"])
        if subj is None or tgt is None:
            return ""
        props = e.get("properties") or {}
        prefix = "WHEREAS " if props.get("preamble") else ""
        subj_shape = props.get("subject_np_shape")
        tgt_shape = props.get("np_shape")
        return (
            prefix
            + _render_noun_phrase(subj, lang=lang, shape=subj_shape)
            + " " + e["relation"] + " "
            + _render_noun_phrase(tgt, lang=lang, shape=tgt_shape)
            + "."
        )

    # Walk nodes in graph order. DEFINED_TERM nodes emit as DEFINE sentences.
    # Operation nodes that are not conjunction-targets start a sentence chain.
    # Stative edges are flushed when we hit a node that appears as either
    # endpoint of an unrendered stative edge.
    def _flush_stative_at(node_id: str) -> None:
        for i, e in enumerate(stative_edges):
            if i in rendered_stative:
                continue
            if e["from_id"] == node_id:
                src = nodes_by_id.get(e["from_id"])
                blank = bool((src or {}).get("properties", {}).get("preceded_by_blank_line"))
                sentences_out.append(("\n" if blank else "") + _emit_stative(e))
                rendered_stative.add(i)

    def _maybe_blank_prefix(node: dict) -> str:
        return "\n" if node.get("properties", {}).get("preceded_by_blank_line") else ""

    for node in graph["nodes"]:
        if node.get("properties", {}).get("defined") is True:
            sentences_out.append(_maybe_blank_prefix(node) + _render_define(node, lang))
            continue
        _flush_stative_at(node["id"])
        if node.get("type") != "TRANSFORM":
            continue
        if node.get("properties", {}).get("operation") is None:
            continue
        op_id = node["id"]
        if op_id in visited_ops or op_id in conj_targets:
            continue

        preamble = bool(node["properties"].get("preamble"))
        leading = node["properties"].get("leading_conjunction")
        # Track clauses and inter-clause conjunctions so multi-clause sentences
        # can be re-broken at canonical SPEC_examples.md formatting (one clause
        # per line, 2-space indented continuation per §1.2 examples).
        first_clause_text = _render_clause(op_id, op_nodes, edges, nodes_by_id, lang,
                                            include_subject=True)
        if preamble:
            first_clause_text = "WHEREAS " + first_clause_text
        elif leading:
            first_clause_text = leading + " " + first_clause_text

        clause_texts: list[str] = [first_clause_text]
        clause_conjunctions: list[str] = []  # length = len(clause_texts) - 1
        clause_depths: list[int] = [0]  # depth of each clause; 0 = top-level
        visited_ops.add(op_id)
        cur = op_id
        prev_subject_id = next(e["from_id"] for e in edges
                                if e["to_id"] == cur and e.get("relation") in MODALS | {"EXECUTES"})
        # Per SPEC §1 examples (e.g. #8): when the parent clause has a
        # leading conjunction (IF / WHEN), the FIRST coordinated clause
        # repeats its subject regardless of inheritance — the gate
        # creates a scope boundary that suppresses elision once.
        clauses_seen_after_leading = 0
        leading_conj_active = leading is not None
        while cur in conj_next:
            conj, nxt = conj_next[cur]
            # Stative continuation
            if nxt not in op_nodes:
                stative_subj = nodes_by_id.get(nxt)
                first_stative = next(
                    (e for e in stative_edges if e["from_id"] == nxt), None
                )
                subj_shape_for_stative = (
                    (first_stative.get("properties") or {}).get("subject_np_shape")
                    if first_stative else None
                )
                stative_parts: list[str] = []
                if stative_subj is not None:
                    stative_parts.append(_render_noun_phrase(stative_subj, lang=lang,
                                                               shape=subj_shape_for_stative))
                for i, e in enumerate(stative_edges):
                    if e["from_id"] == nxt:
                        rendered_stative.add(i)
                        target = nodes_by_id.get(e["to_id"])
                        stative_parts.append(e["relation"])
                        if target is not None:
                            shape = (e.get("properties") or {}).get("np_shape")
                            stative_parts.append(_render_noun_phrase(target, lang=lang, shape=shape))
                clause_conjunctions.append(conj)
                clause_texts.append(" ".join(stative_parts))
                # Stative continuations don't carry their own op; use parent depth + 1
                # if conjunction is subordinating, else parent depth.
                stative_depth = clause_depths[-1] + (1 if conj in SUBORDINATING_CONJUNCTIONS else 0)
                clause_depths.append(stative_depth)
                break
            nxt_subject_edge = next(e for e in edges
                                     if e["to_id"] == nxt and e.get("relation") in MODALS | {"EXECUTES"})
            nxt_subject_id = nxt_subject_edge["from_id"]
            nxt_modal = nxt_subject_edge.get("relation")
            same_subject = nxt_subject_id == prev_subject_id
            inherit = conj in INHERITING_CONJUNCTIONS and same_subject
            include_subject = not inherit
            # Category E: first coordinated clause after a leading IF/WHEN
            # repeats subject (scope boundary).
            if leading_conj_active and clauses_seen_after_leading == 0:
                include_subject = True
            # Category E (PR-B refinement): a clause with its own modal
            # (SHALL/MAY/SHALL_NOT) is a full standalone clause and always
            # repeats its subject. Verb-only continuations (relation=EXECUTES)
            # may inherit per the rule above.
            if nxt_modal in MODALS:
                include_subject = True
            clauses_seen_after_leading += 1
            clause_conjunctions.append(conj)
            clause_texts.append(_render_clause(nxt, op_nodes, edges, nodes_by_id, lang,
                                                 include_subject=include_subject))
            # Read depth from the next op's properties (set by compile per
            # SUBORDINATING_CONJUNCTIONS); fall back to 0 for back-compat.
            nxt_depth = nodes_by_id.get(nxt, {}).get("properties", {}).get("depth", 0)
            clause_depths.append(nxt_depth)
            visited_ops.add(nxt)
            prev_subject_id = nxt_subject_id
            cur = nxt

        # Assemble: single-clause inline; multi-clause one per line with
        # depth-aware indentation per SPEC_examples.md.
        # Indent = 2 * max(depth, 1) spaces:
        #   depth 0 (coordinating continuation, e.g. THEN at parent level): 2 sp
        #   depth 1 (first subordinate, e.g. UNLESS in #2 / #16): 2 sp
        #   depth 2 (PROVIDED_THAT under UNLESS in #16): 4 sp
        #   depth 3 (EXCEPT under PROVIDED_THAT in #16): 6 sp
        def _resolve_tail_breaks(text: str, parent_indent: str, is_last_clause: bool) -> str:
            """Replace `\\x00TAIL_BREAK\\x00 ` with newline + indent.

            End-of-sentence tail preps (e.g. SUBJECT_TO at the very end in #7,
            #12) use the same indent as the parent clause's conjunction line.
            Mid-sentence tail preps (e.g. SUBJECT_TO inside #25) use
            parent_indent + 2 (one more level deep).
            """
            extra = "" if is_last_clause else "  "
            replacement_indent = (parent_indent or "  ") + extra
            return text.replace(" \x00TAIL_BREAK\x00 ", f"\n{replacement_indent}")

        n_clauses = len(clause_texts)
        if n_clauses == 1:
            sentence_text = _resolve_tail_breaks(clause_texts[0], "", is_last_clause=True)
        else:
            sentence_text = _resolve_tail_breaks(clause_texts[0], "", is_last_clause=False)
            for i, (conj, txt, depth) in enumerate(zip(
                clause_conjunctions, clause_texts[1:], clause_depths[1:]
            )):
                indent = "  " * max(depth, 1)
                is_last = (i == len(clause_conjunctions) - 1)
                resolved = _resolve_tail_breaks(txt, indent, is_last_clause=is_last)
                sentence_text += f"\n{indent}{conj} {resolved}"
        sentences_out.append(_maybe_blank_prefix(node) + sentence_text + ".")

    output = "\n".join(sentences_out)
    # Sentinel safety: the `\x00TAIL_BREAK\x00` marker is in-band during
    # _render_clause and replaced during sentence assembly. If any survives,
    # an upstream node label or string literal contained `\x00` and broke
    # our placeholder. Refuse to emit ambiguous output.
    if "\x00" in output:
        raise TRLGrammarError(
            "decompile produced output containing a NUL byte; the graph likely "
            "contains a node id or property string with `\\x00`, which collides "
            "with an internal formatting sentinel. Reject the input graph or "
            "sanitize string properties before decompiling."
        )
    return output


# ─── Validate ─────────────────────────────────────────────────────────

# SPEC_grammar.md §2.1 — Subject subcategory + verb subcategory compatibility.
# True = combination is allowed.
_SUBJ_VERB_OK: set[tuple[str, str]] = (
    # Actors can be subjects of any verb subcategory
    {("actors", v) for v in ("transform", "move", "obligate", "permit",
                              "prohibit", "control", "bind", "resolve")}
    # Containers can transform / control / bind
    | {("containers", "transform"), ("containers", "control"), ("containers", "bind")}
    # Artifacts can only be subjects of comparison/existence Control verbs (footnote)
    | {("artifacts", "control")}
    # Boundaries / Outcomes cannot be primary subjects (per spec table)
)

_NEGATIVE_ARTICLES = {"NO", "NONE"}


# PROCESS validator SHALL VALIDATE RECORD graph SUBJECT_TO DATA vocabulary.
def validate(graph: dict, lang: Optional[dict] = None) -> list[str]:
    """Return a list of validation errors. Empty list = valid.

    Implements these SPEC_grammar.md §4 rules:
      Rule 1  — every node has a type from the noun vocabulary (or TRANSFORM)
      Rule 2  — every edge has a relation (TRUG/L preposition or convention)
      Rule 3  — subject-verb compatibility per §2.1
      Rule 7  — modals (SHALL/MAY/SHALL_NOT) require Actor subjects per §2.3
      Rule 11 — no double negation (Negative article + Prohibit modal)

    Rules 4 (verb-object), 5 (adj-noun), 6 (adv-verb), 8 (pronoun resolution),
    9 (SUPERSEDES/EXTENDS type match), 10 (orphan nodes), 12 (pronoun scope)
    are deferred — see TRUGS-DEVELOPMENT issues for tracking.
    """
    if lang is None:
        lang = load_language()
    errors: list[str] = []

    nouns = {w for w, e in lang.items() if e["speech"] == "noun"}
    prepositions = {w for w, e in lang.items() if e["speech"] == "preposition"}
    valid_relations = prepositions | MODALS | CONJUNCTIONS | {"EXECUTES", "ACTS_ON"}

    nodes_by_id = {n.get("id"): n for n in graph.get("nodes", []) if "id" in n}
    edges = graph.get("edges", [])

    def _subcategory_of(noun_word: str) -> Optional[str]:
        e = lang.get(noun_word)
        return e.get("subcategory") if e else None

    # Rules 1 & 2 (existing)
    for n in graph.get("nodes", []):
        if "type" not in n:
            errors.append(f"node {n.get('id', '?')}: missing type")
        elif n["type"] == "TRANSFORM":
            pass
        elif n["type"] not in nouns:
            errors.append(f"node {n.get('id', '?')}: type {n['type']!r} is not a TRL noun")

    for e in edges:
        rel = e.get("relation")
        if not rel:
            errors.append(f"edge {e.get('from_id')} → {e.get('to_id')}: missing relation")
        elif rel not in valid_relations:
            errors.append(f"edge {e.get('from_id')} → {e.get('to_id')}: unknown relation {rel!r}")

    # Rules 3, 7, 11 — operate per operation node (TRANSFORM with operation prop)
    op_nodes = [n for n in graph.get("nodes", [])
                if n.get("type") == "TRANSFORM"
                and n.get("properties", {}).get("operation")]
    for op in op_nodes:
        op_id = op["id"]
        verb_sub = op.get("properties", {}).get("verb_subcategory")
        # Find the subject edge for this op
        subj_edge = next(
            (e for e in edges if e.get("to_id") == op_id
             and e.get("relation") in MODALS | {"EXECUTES"}),
            None,
        )
        if subj_edge is None or verb_sub is None:
            continue
        subj_node = nodes_by_id.get(subj_edge.get("from_id"))
        if subj_node is None:
            continue
        subj_type = subj_node.get("type")
        subj_sub = _subcategory_of(subj_type)

        # Rule 3 — subject-verb compatibility
        if subj_sub and (subj_sub, verb_sub) not in _SUBJ_VERB_OK:
            errors.append(
                f"op {op_id}: subject {subj_type!r} ({subj_sub}) cannot perform "
                f"{op['properties']['operation']!r} ({verb_sub} verb) — §2.1"
            )

        # Rule 7 — modals require Actor subjects
        modal = subj_edge.get("relation")
        if modal in MODALS and subj_sub != "actors":
            errors.append(
                f"op {op_id}: modal {modal!r} on non-Actor subject {subj_type!r} "
                f"({subj_sub}) — §2.3"
            )

        # Rule 11 — no double negation (Negative article + Prohibit modal)
        if modal == "SHALL_NOT":
            np_shape = (subj_edge.get("properties") or {}).get("np_shape") or {}
            if np_shape.get("article") in _NEGATIVE_ARTICLES:
                errors.append(
                    f"op {op_id}: double negation — Negative article "
                    f"{np_shape['article']!r} with SHALL_NOT modal — §4.11"
                )

    return errors


# ─── CLI ──────────────────────────────────────────────────────────────

# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main(argv: Optional[list] = None) -> int:
    """CLI entry point for `trugs-trl` (compile / decompile / validate).

    Exit codes:
      0 — success
      1 — validation errors
      2 — input error (file not found, malformed JSON, TRUG/L syntax/grammar error)
    """
    parser = argparse.ArgumentParser(
        prog="trugs-trl",
        description="TRL compiler — compile/decompile/validate TRL ↔ TRUG.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd, help_text in [("compile", "Compile TRL to TRUG JSON"),
                            ("decompile", "Decompile TRUG JSON to TRL"),
                            ("validate", "Validate a TRUG JSON")]:
        sp = sub.add_parser(cmd, help=help_text)
        sp.add_argument("file", help="input file, or - for stdin")
    ns = parser.parse_args(argv)

    # Read input — friendly error on missing file
    try:
        src = sys.stdin.read() if ns.file == "-" else Path(ns.file).read_text()
    except FileNotFoundError as e:
        print(f"error: input file not found: {e.filename}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error: could not read input: {e}", file=sys.stderr)
        return 2

    def _parse_json_input() -> object:
        try:
            return json.loads(src)
        except json.JSONDecodeError as e:
            print(
                f"error: input is not valid JSON ({e.msg} at line {e.lineno}, col {e.colno}). "
                "Did you pass a `.trl` file to a JSON-input command?",
                file=sys.stderr,
            )
            sys.exit(2)

    try:
        if ns.command == "compile":
            print(json.dumps(compile(src), indent=2))
        elif ns.command == "decompile":
            print(decompile(_parse_json_input()))
        elif ns.command == "validate":
            errors = validate(_parse_json_input())
            for err in errors:
                print(f"  {err}", file=sys.stderr)
            if errors:
                print(f"{len(errors)} validation error(s)", file=sys.stderr)
                return 1
            print("valid")
    except TRLError as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
