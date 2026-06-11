# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Build language.trug.json from SPEC_vocabulary.md.

Parses the canonical vocabulary spec (211 words across 9 parts of speech)
and emits a fully-populated language TRUG that the TRL compiler can consume.

Re-run this whenever SPEC_vocabulary.md changes. The output file is a
deterministic function of the spec.

Usage:
    python3 tools/build_language_trug.py \\
        TRUGS_LANGUAGE/SPEC_vocabulary.md \\
        TRUGS_LANGUAGE/language.trug.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Widened from `(\w+)` to `([\w ]+?)` (non-greedy) to match the multi-word
# heading "Level Prefixes" added for TRUGS 2.0 (TRUGS-DEVELOPMENT#1719).
PART_HEADING_RE = re.compile(r"^## (\d+)\.\s+([\w ]+?)(?:\s+—\s+([^()]+))?\s*\((\d+)\)\s*$")
SUBCAT_HEADING_RE = re.compile(r"^### ([\w/ ]+?)\s*\((\d+)\)(?:\s+—\s+(.+))?\s*$")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")

# Plural→singular map for part-of-speech headings. Explicit because
# `rstrip("s")` gives wrong answers for irregular plurals
# (e.g. "Prefixes" → "Prefixe").
PART_HEADING_NORMALIZE = {
    "nouns": "noun",
    "verbs": "verb",
    "adjectives": "adjective",
    "adverbs": "adverb",
    "prepositions": "preposition",
    "conjunctions": "conjunction",
    "articles": "article",
    "pronouns": "pronoun",
    "level prefixes": "level_prefix",
}

# Singular→plural map for part-of-speech container IDs. The default
# `f"{p}s"` produces wrong forms for "level_prefix" (would emit
# "level_prefixs" instead of "level_prefixes").
PART_PLURAL = {
    "noun": "nouns",
    "verb": "verbs",
    "adjective": "adjectives",
    "adverb": "adverbs",
    "preposition": "prepositions",
    "conjunction": "conjunctions",
    "article": "articles",
    "pronoun": "pronouns",
    "level_prefix": "level_prefixes",
}

# SI factor strings (as they appear in the spec) to numeric form.
# Used to produce a `factor` property on level_prefix word nodes.
LEVEL_PREFIX_FACTOR = {
    "10²⁴": "1e24", "10²¹": "1e21", "10¹⁸": "1e18", "10¹⁵": "1e15",
    "10¹²": "1e12", "10⁹": "1e9", "10⁶": "1e6", "10³": "1e3",
    "10²": "1e2", "10¹": "1e1", "10⁰": "1e0",
    "10⁻¹": "1e-1", "10⁻²": "1e-2", "10⁻³": "1e-3", "10⁻⁶": "1e-6",
    "10⁻⁹": "1e-9", "10⁻¹²": "1e-12", "10⁻¹⁵": "1e-15",
    "10⁻¹⁸": "1e-18", "10⁻²¹": "1e-21", "10⁻²⁴": "1e-24",
}


def _parse_row(line: str) -> Optional[tuple]:
    """Return (number, word, source, definition, core_flag) for a word row.

    Handles three spec formats:
      5 cols: | # | WORD | source | definition | core |
      4 cols: | # | WORD | source | definition |
      3 cols: | # | WORD | definition |           (articles section)
    Returns None for non-matching lines (e.g. header separator rows).
    """
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if not cells or not cells[0].isdigit():
        return None
    if len(cells) < 3:
        return None
    number = int(cells[0])
    word = cells[1]
    if not re.fullmatch(r"[A-Z_]+", word):
        return None
    if len(cells) == 3:
        source, definition, core = "", cells[2], ""
    elif len(cells) == 4:
        source, definition, core = cells[2], cells[3], ""
    else:
        source, definition, core = cells[2], cells[3], cells[4]
    return number, word, source, definition, core == "yes"


# PROCESS parser SHALL READ STRING DATA spec THEN RETURN ALL RECORD word.
def parse_spec(spec_text: str) -> list[dict]:
    """Return list of word records in document order.

    Each record: {number, word, part_of_speech, subcategory, source, definition, core}
    """
    records: list[dict] = []
    current_part: Optional[str] = None
    current_subcat: Optional[str] = None
    current_subcat_desc: Optional[str] = None

    for line in spec_text.splitlines():
        m = PART_HEADING_RE.match(line)
        if m:
            raw = m.group(2).strip().lower()
            current_part = PART_HEADING_NORMALIZE.get(raw)
            if current_part is None:
                # Default: spaces → underscores, strip trailing 's'.
                # Acceptable for regular plurals not in the explicit map.
                current_part = raw.replace(" ", "_").rstrip("s")
            current_subcat = None
            current_subcat_desc = None
            continue

        m = SUBCAT_HEADING_RE.match(line)
        if m:
            current_subcat = m.group(1).strip().lower().replace(" ", "_")
            current_subcat_desc = (m.group(3) or "").strip()
            continue

        row = _parse_row(line)
        if row and current_part:
            number, word, source, definition, core = row
            records.append({
                "number": number,
                "word": word,
                "part_of_speech": current_part,
                "subcategory": current_subcat or current_part,
                "subcategory_description": current_subcat_desc or "",
                "source": source,
                "definition": definition,
                "core": core,
            })

    return records


# PROCESS builder SHALL MAP ALL RECORD word TO RECORD graph.
def build_trug(records: list[dict]) -> dict:
    """Assemble language.trug.json from parsed records."""
    parts_order: list[str] = []
    subcats_order: dict[str, list[str]] = {}

    for r in records:
        part = r["part_of_speech"]
        sub = r["subcategory"]
        if part not in parts_order:
            parts_order.append(part)
            subcats_order[part] = []
        if sub not in subcats_order[part]:
            subcats_order[part].append(sub)

    nodes: list[dict] = []
    edges: list[dict] = []

    # Root
    nodes.append({
        "id": "language",
        "type": "NAMESPACE",
        "parent_id": None,
        "contains": [PART_PLURAL.get(p, f"{p}s") for p in parts_order],
        "properties": {"name": "TRUGS Language (TRL)", "version": "2.0.0", "word_count": len(records)},
        "metric_level": "KILO_LANGUAGE",
        "dimension": {},
    })

    # Part-of-speech containers
    for part in parts_order:
        part_id = PART_PLURAL.get(part, f"{part}s")
        part_records = [r for r in records if r["part_of_speech"] == part]
        subcat_ids = [f"{part}-{s}" for s in subcats_order[part]]
        nodes.append({
            "id": part_id,
            "type": "DATA",
            "parent_id": "language",
            "contains": subcat_ids,
            "properties": {"speech": part, "count": len(part_records)},
            "metric_level": "HECTO_CATEGORY",
            "dimension": {},
        })

    # Subcategory containers
    for part in parts_order:
        for sub in subcats_order[part]:
            sub_id = f"{part}-{sub}"
            sub_records = [r for r in records if r["part_of_speech"] == part and r["subcategory"] == sub]
            word_ids = [f"w-{r['word'].lower()}" for r in sub_records]
            desc = sub_records[0]["subcategory_description"] if sub_records else ""
            nodes.append({
                "id": sub_id,
                "type": "DATA",
                "parent_id": PART_PLURAL.get(part, f"{part}s"),
                "contains": word_ids,
                "properties": {
                    "subcategory": sub,
                    "description": desc,
                    "count": len(sub_records),
                },
                "metric_level": "DEKA_SUBCATEGORY",
                "dimension": {},
            })

    # Word nodes
    for r in records:
        props = {
            "word": r["word"],
            "number": r["number"],
            "speech": r["part_of_speech"],
            "subcategory": r["subcategory"],
            "source": r["source"],
            "definition": r["definition"],
            "core": r["core"],
        }
        # Level prefixes use a 4-col Factor table format in the spec
        # (#, Word, Factor, Definition). _parse_row mapped cells[2]
        # ("Factor") into source. Re-interpret: source = "shared" by
        # convention (level prefixes have no domain), factor goes into
        # its own property, and definition is enriched with the factor
        # so each row carries a meaningful definition (most spec rows
        # leave the Definition cell empty in the macro/micro tables).
        if r["part_of_speech"] == "level_prefix":
            factor_str = props["source"]
            props["source"] = "shared"
            props["factor"] = LEVEL_PREFIX_FACTOR.get(factor_str, factor_str)
            bare = props["definition"].strip()
            if r["word"] == "BASE":
                # BASE has a bespoke definition; preserve verbatim if present.
                props["definition"] = bare or "Default consumption level"
            elif bare:
                props["definition"] = f"SI prefix {factor_str} — {bare.lower()}"
            else:
                props["definition"] = f"SI prefix {factor_str}"
        nodes.append({
            "id": f"w-{r['word'].lower()}",
            "type": "DATA",
            "parent_id": f"{r['part_of_speech']}-{r['subcategory']}",
            "contains": [],
            "properties": props,
            "metric_level": "BASE_WORD",
            "dimension": {},
        })

    trug = {
        "name": "TRUGS Language Vocabulary",
        "version": "2.0.0",
        "type": "NAMESPACE",
        "description": "Canonical TRL vocabulary — 211 words across 9 parts of speech. Generated from SPEC_vocabulary.md by tools/build_language_trug.py. v2.0.0 adds 21 SI level prefixes for hierarchy transition markers (TRUGS-DEVELOPMENT#1719).",
        "dimensions": {},
        "capabilities": {"vocabularies": ["trl_v2"]},
        "meta": {
            "generated_by": "tools/build_language_trug.py",
            "source": "TRUGS_LANGUAGE/SPEC_vocabulary.md",
            "word_count": len(records),
            "part_counts": {p: sum(1 for r in records if r["part_of_speech"] == p) for p in parts_order},
        },
        "nodes": nodes,
        "edges": edges,
    }
    return trug


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main(argv: Optional[list] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print("usage: build_language_trug.py SPEC.md OUT.json", file=sys.stderr)
        return 2
    spec_path = Path(argv[0])
    out_path = Path(argv[1])
    records = parse_spec(spec_path.read_text())
    trug = build_trug(records)
    out_path.write_text(json.dumps(trug, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {out_path} — {len(records)} words, {len(trug['nodes'])} nodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
