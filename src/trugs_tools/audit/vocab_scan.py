# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Position-independent vocabulary scanner — de-masked TRL vocab drift.

Companion to :mod:`trugs_tools.audit.extract_trl`. Where ``tg audit markdown``
delegates each ``<trl>`` block to the full TRL parser (which raises on the
*first* error per block and stops — so a grammar or syntax error on an early
statement masks any out-of-vocabulary word on a later one), this module does
**no parse at all**. It tokenizes each block and runs the position-independent
membership check :func:`trugs_tools.trl.classify` on every ``WORD`` token,
collecting *every* out-of-vocabulary token regardless of the block's
syntactic or grammatical validity.

This is the SP1 instrument for AAA #2018 (de-masked per-class TRL drift
re-measurement). Vocabulary membership is position-independent, so no parser
change is required — only tokenize + classify, reusing existing
``trugs_tools.trl`` primitives.

Why this de-masks:
- ``classify`` is a pure membership test on a single ``WORD``; it never looks
  at neighbouring tokens, so grammar errors (wrong part of speech, pronoun
  misuse) and parse-level syntax errors (missing terminator, bad structure)
  — which only surface *during* ``parse`` — cannot hide a vocab miss here.
- The one residual masking source is a *tokenize-level* syntax error (an
  unterminated string literal or an unexpected character), which makes
  ``tokenize`` itself raise before it reaches later tokens. We recover from
  that by re-scanning the block line by line and skipping only the offending
  line(s), so a single malformed line cannot mask vocab misses elsewhere in
  the block. Such recovery is flagged per block (``tokenize_recovered``).

Reporting only — never edits source markdown. JSON output feeds the AAA #2018
de-masking extraction (SP3): each miss occurrence carries its source file +
block so downstream tooling can emit ``DRIFT_EVENT`` nodes and compute
evidential burden (events × distinct files).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

from trugs_tools.trl import (
    TRLSyntaxError,
    TRLVocabularyError,
    classify,
    load_language,
    tokenize,
)
from trugs_tools.audit.extract_trl import (
    Block,
    MARKDOWN_SUFFIXES,
    extract_blocks,
)

__all__ = [
    "VocabMiss",
    "BlockVocab",
    "FileVocab",
    "scan_block",
    "scan_file",
    "scan_path",
    "main",
]


@dataclass(frozen=True)
class VocabMiss:
    """One out-of-vocabulary ``WORD`` token occurrence within a block.

    ``line`` / ``col`` are 1-based and relative to the block *content* (the
    text between the ``<trl>`` and ``</trl>`` tags), matching the offsets
    :func:`trugs_tools.trl.tokenize` produces.
    """

    token: str
    line: int
    col: int


@dataclass(frozen=True)
class BlockVocab:
    """Vocabulary-scan outcome for one extracted block."""

    block: Block
    misses: list[VocabMiss]
    tokenize_recovered: bool = False  # True if a tokenize-level syntax error forced line-by-line recovery


@dataclass
class FileVocab:
    """Aggregated vocabulary-scan outcomes for one markdown file."""

    path: str
    blocks: list[BlockVocab] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @property
    def miss_count(self) -> int:
        return sum(len(b.misses) for b in self.blocks)


def _collect_misses(tokens: Iterable, lang: dict, line: Optional[int] = None) -> list[VocabMiss]:
    """Collect every out-of-vocab ``WORD`` token. ``line`` overrides the token
    line when scanning a single recovered line (whose tokens all report line 1)."""
    misses: list[VocabMiss] = []
    for tok in tokens:
        if tok.kind != "WORD":
            continue
        try:
            classify(tok.value, lang)
        except TRLVocabularyError:
            misses.append(VocabMiss(
                token=tok.value,
                line=line if line is not None else tok.line,
                col=tok.col,
            ))
    return misses


def scan_block(content: str, lang: dict) -> BlockVocab:
    """Scan one block's content for out-of-vocab WORD tokens, position-independently.

    Returns a :class:`BlockVocab` carrying every miss. No parse is performed;
    grammar and parse-level syntax state are irrelevant. A tokenize-level
    syntax error triggers line-by-line recovery (flagged via
    ``tokenize_recovered``) so it cannot mask misses on other lines.

    The ``block`` field is filled by the caller (:func:`scan_file`); this
    helper takes raw content so it is unit-testable in isolation.
    """
    try:
        tokens = tokenize(content)
        return BlockVocab(block=None, misses=_collect_misses(tokens, lang), tokenize_recovered=False)  # type: ignore[arg-type]
    except TRLSyntaxError:
        misses: list[VocabMiss] = []
        for lineno, line_src in enumerate(content.splitlines(), start=1):
            try:
                line_tokens = tokenize(line_src)
            except TRLSyntaxError:
                continue
            misses.extend(_collect_misses(line_tokens, lang, line=lineno))
        return BlockVocab(block=None, misses=misses, tokenize_recovered=True)  # type: ignore[arg-type]


def scan_file(path: Path, lang: dict) -> FileVocab:
    """Extract and vocabulary-scan every ``<trl>`` block in one markdown file."""
    source = path.read_text(encoding="utf-8")
    blocks = extract_blocks(source)
    out: list[BlockVocab] = []
    for b in blocks:
        bv = scan_block(b.content, lang)
        out.append(BlockVocab(block=b, misses=bv.misses, tokenize_recovered=bv.tokenize_recovered))
    return FileVocab(path=str(path), blocks=out)


def _iter_markdown(root: Path) -> Iterator[Path]:
    if root.is_file():
        if root.suffix.lower() in MARKDOWN_SUFFIXES:
            yield root
        return
    for suffix in MARKDOWN_SUFFIXES:
        yield from sorted(root.rglob(f"*{suffix}"))


def scan_path(root: Path, lang: dict) -> list[FileVocab]:
    """Vocabulary-scan every markdown file under ``root`` (or ``root`` itself)."""
    return [scan_file(p, lang) for p in _iter_markdown(root)]


# ─── Output formatting ──────────────────────────────────────────────────

def _format_text(results: Iterable[FileVocab], verbose: bool) -> str:
    lines: list[str] = []
    total_blocks = 0
    total_misses = 0
    files_with_misses = 0
    recovered_blocks = 0
    distinct: set[str] = set()
    for r in results:
        total_blocks += r.block_count
        total_misses += r.miss_count
        recovered_blocks += sum(1 for b in r.blocks if b.tokenize_recovered)
        for b in r.blocks:
            distinct.update(m.token for m in b.misses)
        if r.miss_count == 0:
            if verbose and r.block_count:
                lines.append(f"{r.path}: {r.block_count} block(s) — 0 vocab misses")
            continue
        files_with_misses += 1
        lines.append(f"{r.path}: {r.miss_count} vocab miss(es) across {r.block_count} block(s)")
        for b in r.blocks:
            if not b.misses:
                continue
            tag = " [tokenize-recovered]" if b.tokenize_recovered else ""
            toks = ", ".join(f"{m.token}@{m.line}:{m.col}" for m in b.misses)
            lines.append(
                f"  block #{b.block.index} (lines {b.block.open_line}-{b.block.close_line}){tag}: {toks}"
            )
    lines.append("")
    lines.append(
        f"Summary: {total_misses} vocab miss(es) ({len(distinct)} distinct) across "
        f"{total_blocks} block(s); {files_with_misses} file(s) with misses; "
        f"{recovered_blocks} block(s) needed tokenize recovery"
    )
    return "\n".join(lines)


def _format_json(results: Iterable[FileVocab]) -> str:
    results = list(results)
    files = []
    for r in results:
        files.append({
            "path": r.path,
            "block_count": r.block_count,
            "miss_count": r.miss_count,
            "blocks": [
                {
                    "index": b.block.index,
                    "open_line": b.block.open_line,
                    "close_line": b.block.close_line,
                    "tokenize_recovered": b.tokenize_recovered,
                    "misses": [
                        {"token": m.token, "line": m.line, "col": m.col}
                        for m in b.misses
                    ],
                }
                for b in r.blocks
            ],
        })
    distinct: set[str] = set()
    for r in results:
        for b in r.blocks:
            distinct.update(m.token for m in b.misses)
    payload = {
        "files": files,
        "totals": {
            "files_scanned": len(files),
            "files_with_misses": sum(1 for f in files if f["miss_count"] > 0),
            "blocks_total": sum(f["block_count"] for f in files),
            "miss_occurrences": sum(f["miss_count"] for f in files),
            "distinct_miss_tokens": len(distinct),
            "blocks_tokenize_recovered": sum(
                1 for f in files for b in f["blocks"] if b["tokenize_recovered"]
            ),
        },
    }
    return json.dumps(payload, indent=2)


# ─── CLI ─────────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    """``tg audit vocab PATH [--format text|json] [--language PATH]``.

    Position-independent vocabulary scan: collects every out-of-vocabulary
    ``WORD`` token across all ``<trl>`` blocks under PATH, with no parse, so
    grammar/syntax errors cannot mask vocab drift. Reporting only.

    Exit codes:
        0 — no out-of-vocabulary tokens found
        1 — one or more out-of-vocabulary tokens found
        2 — invocation error (bad path, bad args)
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="tg audit vocab",
        description=(
            "Tokenize every <trl> block under PATH and report every "
            "out-of-vocabulary WORD token (position-independent membership "
            "check — no parse, so grammar/syntax errors cannot mask vocab "
            "drift). Reporting only — never modifies source files."
        ),
    )
    parser.add_argument(
        "path",
        help="File or directory to scan (markdown only; recurses into directories)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="In text mode, also list scanned files with zero vocab misses",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Path to an alternate language.trug.json (default: packaged vocabulary)",
    )

    args = parser.parse_args(argv)
    root = Path(args.path)
    if not root.exists():
        print(f"tg audit vocab: path does not exist: {root}", file=sys.stderr)
        return 2

    lang = load_language(args.language)
    results = scan_path(root, lang)
    if args.format == "json":
        print(_format_json(results))
    else:
        print(_format_text(results, verbose=args.verbose))

    miss_count = sum(r.miss_count for r in results)
    return 1 if miss_count > 0 else 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())
