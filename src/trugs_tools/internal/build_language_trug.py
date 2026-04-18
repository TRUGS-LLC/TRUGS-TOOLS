"""Build language.trug.json from SPEC_vocabulary.md.

Parses the canonical vocabulary spec (190 words across 8 parts of speech)
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

PART_HEADING_RE = re.compile(r"^## (\d+)\.\s+(\w+)(?:\s+—\s+([^()]+))?\s*\((\d+)\)\s*$")
SUBCAT_HEADING_RE = re.compile(r"^### ([\w/ ]+?)\s*\((\d+)\)(?:\s+—\s+(.+))?\s*$")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")


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
            current_part = m.group(2).lower().rstrip("s")
            # Normalise "Nouns" -> "noun", etc.
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
        "contains": [f"{p}s" for p in parts_order],
        "properties": {"name": "TRUGS Language (TRL)", "version": "1.0.1", "word_count": len(records)},
        "metric_level": "KILO_LANGUAGE",
        "dimension": {},
    })

    # Part-of-speech containers
    for part in parts_order:
        part_id = f"{part}s"
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
                "parent_id": f"{part}s",
                "contains": word_ids,
                "properties": {
                    "subcategory": sub,
                    "description": desc,
                    "count": len(sub_records),
                },
                "metric_level": "DECA_SUBCATEGORY",
                "dimension": {},
            })

    # Word nodes
    for r in records:
        nodes.append({
            "id": f"w-{r['word'].lower()}",
            "type": "DATA",
            "parent_id": f"{r['part_of_speech']}-{r['subcategory']}",
            "contains": [],
            "properties": {
                "word": r["word"],
                "number": r["number"],
                "speech": r["part_of_speech"],
                "subcategory": r["subcategory"],
                "source": r["source"],
                "definition": r["definition"],
                "core": r["core"],
            },
            "metric_level": "BASE_WORD",
            "dimension": {},
        })

    trug = {
        "name": "TRUGS Language Vocabulary",
        "version": "1.0.1",
        "type": "NAMESPACE",
        "description": "Canonical TRL vocabulary — 190 words across 8 parts of speech. Generated from SPEC_vocabulary.md by tools/build_language_trug.py.",
        "dimensions": {},
        "capabilities": {"vocabularies": ["trl_v1"]},
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
