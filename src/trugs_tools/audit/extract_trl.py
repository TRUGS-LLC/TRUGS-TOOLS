# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Markdown <trl> block extractor — bridge from markdown corpus to TRL parser.

Walks a path of markdown files, extracts every ``<trl>...</trl>`` fenced block,
and delegates each block to the canonical TRL parser at
:mod:`trugs_tools.trl`. Aggregates per-file / per-block results into a report
with both human-readable and JSON formats.

Reporting only — never edits the source markdown. Failures are aggregated for
downstream tooling (the v2.0 vocabulary RFC pass uses the JSON output to
classify drift per `mem-drift-as-evidence-epistemics`).

Block extraction:
- Two recognized forms (matching the "fenced block" convention used
  throughout AGENT/, AAA/, REFERENCE/STANDARD_*.md):

  1. **Multi-line** — ``<trl>`` alone on a line (whitespace allowed),
     content on following lines, ``</trl>`` alone on a closing line.
  2. **Inline** — ``<trl>...</trl>`` with both tags on the same line.

  A ``<trl>`` token appearing mid-prose (e.g. in a sentence describing the
  tag) is intentionally NOT treated as an opening tag, so corpus mentions
  of the tag don't trigger false-positive extraction. This matches how
  markdown code fences work.
- Code fences (``` ... ```) are NOT special — a ``<trl>`` inside a fenced
  code block is still extracted (when it satisfies the line-anchored form
  above). This is intentional: the corpus contains TRL inside fenced
  examples that should still validate.
- Nested ``<trl>`` blocks are not part of the spec — the first ``</trl>``
  after an opening ``<trl>`` closes the block.

Parser delegation:
- Uses :func:`trugs_tools.trl.compile`. Compile is the strongest validation
  gate available (parse + classify + grammar + graph emission). A block
  that compiles cleanly is valid TRL.
- :class:`trugs_tools.trl.TRLError` and subclasses are caught and reported
  per block; the audit never raises on a malformed block.

Line numbers in :class:`Block` and :class:`BlockResult` are 1-based and refer
to the source markdown file (the line containing ``<trl>`` is ``open_line``;
the line containing ``</trl>`` is ``close_line``).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

from trugs_tools.trl import (
    TRLError,
    ParseError,
    collect_errors,
    compile as trl_compile,
    load_language,
)

__all__ = [
    "Block",
    "BlockResult",
    "FileResult",
    "extract_blocks",
    "audit_file",
    "audit_path",
    "MARKDOWN_SUFFIXES",
    # --all-errors path (AAA #2018 SP2) — additive; default path is unchanged
    "BlockErrors",
    "FileErrors",
    "audit_file_all_errors",
    "audit_path_all_errors",
]

MARKDOWN_SUFFIXES = (".md", ".markdown")

# Line-anchored: open tag alone on its line (whitespace allowed before/after).
# A `<trl>` mid-prose ("the `<trl>` block") does NOT match and is ignored.
_OPEN_LINE_RE = re.compile(r"^\s*<trl>\s*$", re.IGNORECASE)
_CLOSE_LINE_RE = re.compile(r"^\s*</trl>\s*$", re.IGNORECASE)
# Inline form: open + close on the same line; non-greedy body in between.
_INLINE_RE = re.compile(r"<trl>(.*?)</trl>", re.IGNORECASE)


@dataclass(frozen=True)
class Block:
    """A single extracted ``<trl>...</trl>`` block.

    ``content`` is the raw text between the open and close tags, with leading
    and trailing whitespace preserved so the parser sees the same source the
    author wrote.
    """

    index: int            # 0-based index within the file
    open_line: int        # 1-based line of <trl>
    close_line: int       # 1-based line of </trl>
    content: str          # raw block content (between tags, exclusive)


@dataclass(frozen=True)
class BlockResult:
    """Outcome of parsing one extracted block."""

    block: Block
    ok: bool
    error_type: Optional[str] = None    # e.g. "TRLSyntaxError"
    error_message: Optional[str] = None


@dataclass
class FileResult:
    """Aggregated outcomes for one markdown file."""

    path: str
    blocks: list[BlockResult] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.blocks if r.ok)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.blocks if not r.ok)


def extract_blocks(source: str) -> list[Block]:
    """Pull every ``<trl>...</trl>`` block out of a markdown source string.

    Two recognized forms (per module docstring): line-anchored multi-line
    and inline single-line. ``<trl>`` mentions in prose are ignored.

    The first ``</trl>`` after an opening ``<trl>`` closes the block; a
    stray ``<trl>`` with no matching close stops extraction at end-of-file
    and that block is omitted from the result (malformed-fence handling).
    """
    blocks: list[Block] = []
    lines = source.splitlines()
    i = 0
    n = len(lines)
    next_index = 0

    while i < n:
        line = lines[i]

        # Inline form first — ``<trl>...</trl>`` on a single line.
        # Multiple inline blocks per line are allowed.
        if _INLINE_RE.search(line):
            for m in _INLINE_RE.finditer(line):
                blocks.append(Block(
                    index=next_index,
                    open_line=i + 1,
                    close_line=i + 1,
                    content=m.group(1),
                ))
                next_index += 1
            i += 1
            continue

        # Multi-line form — open tag alone on its line.
        if not _OPEN_LINE_RE.match(line):
            i += 1
            continue

        open_line = i + 1  # 1-based
        body_parts: list[str] = []
        j = i + 1
        close_line: Optional[int] = None
        while j < n:
            if _CLOSE_LINE_RE.match(lines[j]):
                close_line = j + 1  # 1-based
                break
            body_parts.append(lines[j])
            j += 1

        if close_line is None:
            # Unterminated block — drop per docstring
            break

        blocks.append(Block(
            index=next_index,
            open_line=open_line,
            close_line=close_line,
            content="\n".join(body_parts),
        ))
        next_index += 1
        i = close_line  # resume scanning after the </trl> line

    return blocks


def _validate_block(block: Block) -> BlockResult:
    src = block.content.strip()
    if not src:
        # An empty block is treated as a pass (no TRL to validate). The
        # extractor's job is to surface blocks the author intended as TRL;
        # an empty block carries no claims and so cannot fail.
        return BlockResult(block=block, ok=True)
    try:
        trl_compile(src)
    except TRLError as exc:
        return BlockResult(
            block=block,
            ok=False,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    return BlockResult(block=block, ok=True)


def audit_file(path: Path) -> FileResult:
    """Extract and validate every ``<trl>`` block in one markdown file."""
    source = path.read_text(encoding="utf-8")
    blocks = extract_blocks(source)
    return FileResult(
        path=str(path),
        blocks=[_validate_block(b) for b in blocks],
    )


def _iter_markdown(root: Path) -> Iterator[Path]:
    if root.is_file():
        if root.suffix.lower() in MARKDOWN_SUFFIXES:
            yield root
        return
    for suffix in MARKDOWN_SUFFIXES:
        yield from sorted(root.rglob(f"*{suffix}"))


def audit_path(root: Path) -> list[FileResult]:
    """Audit every markdown file under ``root`` (or ``root`` itself if a file).

    Files with zero ``<trl>`` blocks are still represented in the result so
    callers can distinguish "no blocks found" from "file not scanned".
    """
    return [audit_file(p) for p in _iter_markdown(root)]


# ─── Output formatting ──────────────────────────────────────────────────

def _format_text(results: Iterable[FileResult], verbose: bool) -> str:
    lines: list[str] = []
    total_blocks = 0
    total_pass = 0
    total_fail = 0
    files_with_blocks = 0
    for r in results:
        total_blocks += r.block_count
        total_pass += r.pass_count
        total_fail += r.fail_count
        if r.block_count == 0:
            if verbose:
                lines.append(f"{r.path}: 0 blocks")
            continue
        files_with_blocks += 1
        status = "OK" if r.fail_count == 0 else "FAIL"
        lines.append(f"{r.path}: {r.block_count} block(s) — {r.pass_count} pass, {r.fail_count} fail [{status}]")
        for br in r.blocks:
            if not br.ok:
                lines.append(
                    f"  block #{br.block.index} (lines {br.block.open_line}-{br.block.close_line}): "
                    f"{br.error_type}: {br.error_message}"
                )
            elif verbose:
                lines.append(
                    f"  block #{br.block.index} (lines {br.block.open_line}-{br.block.close_line}): OK"
                )
    lines.append("")
    lines.append(
        f"Summary: {total_blocks} block(s) across {files_with_blocks} file(s) "
        f"with blocks — {total_pass} pass, {total_fail} fail"
    )
    return "\n".join(lines)


def _format_json(results: Iterable[FileResult]) -> str:
    payload = {
        "files": [
            {
                "path": r.path,
                "block_count": r.block_count,
                "pass_count": r.pass_count,
                "fail_count": r.fail_count,
                "blocks": [
                    {
                        "index": br.block.index,
                        "open_line": br.block.open_line,
                        "close_line": br.block.close_line,
                        "ok": br.ok,
                        "error_type": br.error_type,
                        "error_message": br.error_message,
                    }
                    for br in r.blocks
                ],
            }
            for r in results
        ],
    }
    totals = {
        "files_scanned": len(payload["files"]),
        "files_with_blocks": sum(1 for f in payload["files"] if f["block_count"] > 0),
        "blocks_total": sum(f["block_count"] for f in payload["files"]),
        "blocks_pass": sum(f["pass_count"] for f in payload["files"]),
        "blocks_fail": sum(f["fail_count"] for f in payload["files"]),
    }
    payload["totals"] = totals
    return json.dumps(payload, indent=2)


# ─── --all-errors path (AAA #2018 SP2) ────────────────────────────────────
# Opt-in error-recovery reporting: instead of the first error per block, list
# EVERY statement-level error tagged by class (vocab / grammar / syntax). This
# is a SEPARATE code path from the default audit above so the default output is
# byte-identical (INVARIANT default_parse SHALL_NOT CHANGE).

@dataclass(frozen=True)
class BlockErrors:
    """All recovered errors for one extracted block (via trl.collect_errors)."""

    block: Block
    errors: list[ParseError]


@dataclass
class FileErrors:
    """Aggregated all-errors outcomes for one markdown file."""

    path: str
    blocks: list[BlockErrors] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @property
    def error_count(self) -> int:
        return sum(len(b.errors) for b in self.blocks)


def audit_file_all_errors(path: Path, lang: dict) -> FileErrors:
    """Extract every block and collect ALL statement-level errors per block."""
    source = path.read_text(encoding="utf-8")
    blocks = extract_blocks(source)
    return FileErrors(
        path=str(path),
        blocks=[BlockErrors(block=b, errors=collect_errors(b.content, lang)) for b in blocks],
    )


def audit_path_all_errors(root: Path, lang: dict) -> list[FileErrors]:
    """All-errors audit of every markdown file under ``root``."""
    return [audit_file_all_errors(p, lang) for p in _iter_markdown(root)]


def _per_class_count(results: Iterable[FileErrors]) -> dict[str, int]:
    counts = {"TRLVocabularyError": 0, "TRLGrammarError": 0, "TRLSyntaxError": 0}
    for r in results:
        for b in r.blocks:
            for e in b.errors:
                counts[e.error_class] = counts.get(e.error_class, 0) + 1
    return counts


def _format_text_all_errors(results: Iterable[FileErrors], verbose: bool) -> str:
    results = list(results)
    lines: list[str] = []
    total_blocks = 0
    total_errors = 0
    files_with_errors = 0
    for r in results:
        total_blocks += r.block_count
        total_errors += r.error_count
        if r.error_count == 0:
            if verbose and r.block_count:
                lines.append(f"{r.path}: {r.block_count} block(s) — 0 errors")
            continue
        files_with_errors += 1
        lines.append(f"{r.path}: {r.error_count} error(s) across {r.block_count} block(s)")
        for b in r.blocks:
            for e in b.errors:
                lines.append(
                    f"  block #{b.block.index} (lines {b.block.open_line}-{b.block.close_line}): "
                    f"{e.error_class}: {e.message}"
                )
    counts = _per_class_count(results)
    lines.append("")
    lines.append(
        f"Summary: {total_errors} error(s) across {total_blocks} block(s); "
        f"{files_with_errors} file(s) with errors — "
        f"vocab={counts['TRLVocabularyError']}, "
        f"grammar={counts['TRLGrammarError']}, "
        f"syntax={counts['TRLSyntaxError']}"
    )
    return "\n".join(lines)


def _format_json_all_errors(results: Iterable[FileErrors]) -> str:
    results = list(results)
    files = [
        {
            "path": r.path,
            "block_count": r.block_count,
            "error_count": r.error_count,
            "blocks": [
                {
                    "index": b.block.index,
                    "open_line": b.block.open_line,
                    "close_line": b.block.close_line,
                    "errors": [
                        {
                            "error_class": e.error_class,
                            "message": e.message,
                            "line": e.line,
                            "col": e.col,
                        }
                        for e in b.errors
                    ],
                }
                for b in r.blocks
            ],
        }
        for r in results
    ]
    payload = {
        "files": files,
        "totals": {
            "files_scanned": len(files),
            "blocks_total": sum(f["block_count"] for f in files),
            "blocks_with_errors": sum(1 for f in files for b in f["blocks"] if b["errors"]),
            "error_occurrences": sum(f["error_count"] for f in files),
            "per_class_count": _per_class_count(results),
        },
    }
    return json.dumps(payload, indent=2)


# ─── CLI ─────────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    """``tg audit markdown PATH [--format text|json] [--verbose] [--all-errors]``.

    Default mode reports the first error per block (the canonical first-error
    contract). ``--all-errors`` switches to the error-recovery path: every
    statement-level error per block, tagged by class — the de-masked
    grammar/syntax measurement for AAA #2018.

    Exit codes:
        0 — every block passed (no errors)
        1 — one or more blocks failed
        2 — invocation error (bad path, bad args)
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="trug audit markdown",
        description=(
            "Extract every <trl>...</trl> block from markdown files under PATH "
            "and validate each against the canonical TRL parser. Reporting only — "
            "never modifies source files."
        ),
        epilog="""examples:
  trug audit markdown AAA/AAA_1234_plan.md
  trug audit markdown docs/ -f json

exit codes:
  0  all blocks parse
  1  parse failures present
  2  usage error (bad flags or arguments)""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        help="In text mode, also list passing blocks and files with zero blocks",
    )
    parser.add_argument(
        "--all-errors",
        action="store_true",
        help=(
            "Error-recovery mode: report EVERY statement-level error per block "
            "(tagged vocab/grammar/syntax), not just the first. Does not change "
            "the default first-error parser behavior."
        ),
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Path to an alternate language.trug.json (default: packaged vocabulary)",
    )

    args = parser.parse_args(argv)
    root = Path(args.path)
    if not root.exists():
        print(f"tg audit markdown: path does not exist: {root}", file=sys.stderr)
        return 2

    if args.all_errors:
        lang = load_language(args.language)
        results = audit_path_all_errors(root, lang)
        if args.format == "json":
            print(_format_json_all_errors(results))
        else:
            print(_format_text_all_errors(results, verbose=args.verbose))
        error_count = sum(r.error_count for r in results)
        return 1 if error_count > 0 else 0

    results = audit_path(root)
    if args.format == "json":
        print(_format_json(results))
    else:
        print(_format_text(results, verbose=args.verbose))

    fail_count = sum(r.fail_count for r in results)
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())
