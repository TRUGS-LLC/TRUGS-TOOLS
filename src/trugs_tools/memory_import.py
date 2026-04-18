"""TRUGS Memory Import — bulk import flat markdown files into a memory TRUG.

Walks a directory of `*.md` files with YAML frontmatter, extracts
per-file metadata, and writes them into a `memory.trug.json` as TRUG
nodes using the extended schema from PR #13 (`rule`, `rationale`,
`valid_to`, `session_id`, `superseded_by`).

Frontmatter contract expected by default:

    ---
    name: Terse one-line rule (becomes `rule`)
    description: One-sentence summary (becomes `rationale`)
    type: feedback | user | project | reference (becomes `memory_type`)
    ---
    Full prose body (becomes `text`)

Files without frontmatter get imported with:
  - `memory_type` derived from the filename prefix
    (`user_*` → user, `feedback_*` → feedback, …) or `fact` as fallback
  - `text` = full file contents
  - No `rule` or `rationale`

The import is **idempotent**: if a memory already exists in the target
graph with identical `text` content, it is skipped. Re-running against
the same directory picks up new files only.

Usage:
    python tools/memory_import.py <src_dir> <out.trug.json>
                                  [--type-from-filename]
                                  [--tag TAG]
                                  [--source-prefix PREFIX]
                                  [--dry-run]
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from trugs_tools.memory import init_memory_graph, load_graph, remember, save_graph
except ImportError:
    from trugs_tools.memory import init_memory_graph, load_graph, remember, save_graph


# ─── Filename → memory_type mapping ────────────────────────────────────────────

#: Default mapping from filename prefix to canonical memory_type.
#: Only triggered when --type-from-filename is on AND the frontmatter
#: lacks an explicit `type` field.
FILENAME_TYPE_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("user_", "user"),
    ("feedback_", "feedback"),
    ("project_", "project"),
    ("reference_", "reference"),
)


# ─── Frontmatter parser ────────────────────────────────────────────────────────


# AGENT claude SHALL DEFINE RECORD parsed_file AS A RECORD finding.
@dataclass
class ParsedFile:
    """Result of parsing one markdown file for memory import."""

    frontmatter: Dict[str, str]
    body: str

    # AGENT claude SHALL MAP RECORD parsed_file TO STRING DATA name.
    @property
    def name(self) -> Optional[str]:
        return self.frontmatter.get("name")

    # AGENT claude SHALL MAP RECORD parsed_file TO STRING DATA description.
    @property
    def description(self) -> Optional[str]:
        return self.frontmatter.get("description")

    # AGENT claude SHALL MAP RECORD parsed_file TO STRING DATA type.
    @property
    def type(self) -> Optional[str]:
        return self.frontmatter.get("type")


def _strip_yaml_quotes(value: str) -> str:
    """Remove a single enclosing pair of YAML quotes from a value.

    YAML authors commonly wrap values containing colons or other special
    chars: `name: "Format: subtitle"`. The minimal hand-rolled parser
    used to leave the literal quotes in the value, which would then flow
    into `rule` / `rationale` and show up in the rendered MEMORY.md.
    This helper strips matching `"..."` or `'...'` pairs. Nested or
    escaped quotes are NOT expanded — that would require a real YAML
    parser, which is explicitly out of scope (zero runtime deps).
    (Audit #19.)
    """
    if len(value) >= 2:
        if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
            return value[1:-1]
    return value


# PROCESS parser SHALL READ FILE markdown THEN RETURN RECORD parsed_file.
def parse_markdown_with_frontmatter(content: str) -> ParsedFile:
    """Parse a markdown file's YAML frontmatter and body.

    Supports the minimal form needed for memory files:
      - Leading `---` on its own line opens the frontmatter block
      - Trailing `---` on its own line closes it
      - Each line inside is `key: value` (values may contain colons)
      - Lines that don't match `key: value` are ignored

    If there is no frontmatter, returns an empty dict and the full
    content as the body. Does not invoke PyYAML — keeps this module
    dependency-free (important for the zero-deps `trugs` package).
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return ParsedFile(frontmatter={}, body=content.strip())

    end_idx: Optional[int] = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        # Malformed — no closing delimiter. Fall back to treating the
        # whole thing as body so we don't silently drop content.
        return ParsedFile(frontmatter={}, body=content.strip())

    fm_lines = lines[1:end_idx]
    body_lines = lines[end_idx + 1 :]

    frontmatter: Dict[str, str] = {}
    for line in fm_lines:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = _strip_yaml_quotes(value.strip())

    body = "\n".join(body_lines).strip()
    return ParsedFile(frontmatter=frontmatter, body=body)


# ─── Type derivation ───────────────────────────────────────────────────────────


# PROCESS classifier SHALL MATCH RECORD memory TO STRING DATA type.
def derive_memory_type(
    parsed: ParsedFile,
    filename: str,
    *,
    type_from_filename: bool,
) -> str:
    """Determine the `memory_type` for an imported file.

    Order of preference:
      1. `type` field in the frontmatter (always wins when present)
      2. Filename prefix match (only when type_from_filename=True)
      3. Literal `fact` as a safe default
    """
    fm_type = parsed.type
    if fm_type:
        return fm_type.lower()
    if type_from_filename:
        for prefix, memory_type in FILENAME_TYPE_PREFIXES:
            if filename.startswith(prefix):
                return memory_type
    return "fact"


# ─── Import ────────────────────────────────────────────────────────────────────


# AGENT claude SHALL DEFINE RECORD import_report AS A RECORD finding.
@dataclass
class ImportReport:
    """Summary of an import run. Returned by `import_flat_directory`."""

    imported: int = 0
    skipped_duplicate: int = 0
    skipped_malformed: int = 0
    skipped_outside: int = 0  # audit #16 — symlink escaping src_dir
    files_scanned: int = 0
    new_ids: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.new_ids is None:
            self.new_ids = []


def _idempotency_key(text: str, rule: Optional[str], rationale: Optional[str], memory_type: str) -> str:
    """Stable key used to detect duplicates across imports.

    Earlier versions keyed only on `text`, which silently dropped files
    with identical prose bodies but different frontmatter (audit #7).
    The key now folds in `rule`, `rationale`, and `memory_type` so two
    files with the same body but different metadata are preserved as
    distinct memories.
    """
    parts = [text or "", rule or "", rationale or "", (memory_type or "").lower()]
    # L3: SHA-256 hash prevents collisions when fields contain \x1f
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


# PROCESS importer SHALL READ ALL FILE markdown THEN WRITE EACH RECORD memory TO RECORD graph.
def import_flat_directory(
    src_dir: Path,
    out_path: Path,
    *,
    type_from_filename: bool = True,
    tags: Optional[List[str]] = None,
    source_prefix: Optional[str] = None,
    dry_run: bool = False,
    checkpoint_every: int = 50,
) -> ImportReport:
    """Import every `*.md` file under `src_dir` as a memory in `out_path`.

    Args:
        src_dir: directory to walk (recursive). Symlinks that resolve
            outside `src_dir` are skipped for safety (audit #16) and
            counted in `ImportReport.skipped_outside`.
        out_path: memory TRUG output path. Created via `init_memory_graph`
            if it doesn't already exist.
        type_from_filename: when True, derive `memory_type` from the
            filename prefix when the frontmatter lacks a `type` field.
        tags: list of tags to apply to every imported memory (e.g.
            `["migrated-2026-04"]`). Defaults to empty.
        source_prefix: if set, prepended to each memory's `source` property
            (which otherwise contains the path relative to `src_dir`).
        dry_run: if True, scan and report without writing. Still returns
            an accurate count and a list of IDs that WOULD be created
            (synthesized, not actual graph IDs).
        checkpoint_every: save the graph to disk every N successful
            imports, so a Ctrl-C mid-walk preserves partial progress
            (audit #9). `save_graph` is atomic so interruption of the
            checkpoint itself is also safe. Default 50. Ignored for
            dry_run.

            Interrupt contract (audit round 3 R3-6): if this function
            raises BaseException (including KeyboardInterrupt) mid-walk,
            the in-memory `graph` dict contains partial state newer than
            the last on-disk checkpoint. Callers MUST reload from
            `out_path` after catching — do NOT re-save the in-memory
            copy or you will clobber the last checkpoint with
            inconsistent state.

    Returns:
        ImportReport with counts and the list of new memory IDs.
    """
    src_dir = Path(src_dir)
    out_path = Path(out_path)

    if not src_dir.exists() or not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")

    src_dir_resolved = src_dir.resolve()

    if out_path.exists():
        graph = load_graph(out_path)
    else:
        if dry_run:
            # Build an in-memory graph; don't touch disk.
            graph = _make_ephemeral_graph()
        else:
            graph = init_memory_graph(out_path)

    existing_keys = _collect_existing_keys(graph)

    report = ImportReport()
    since_checkpoint = 0
    for path in sorted(src_dir.rglob("*.md")):
        report.files_scanned += 1

        # audit #16 — reject symlinks escaping src_dir BEFORE reading.
        # I2: resolve once, then read from the resolved path to close
        # the TOCTOU window between the security check and the read.
        try:
            resolved = path.resolve()
            resolved.relative_to(src_dir_resolved)
        except (ValueError, OSError):
            report.skipped_outside += 1
            continue

        try:
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            report.skipped_malformed += 1
            continue

        parsed = parse_markdown_with_frontmatter(content)

        # Determine the text we'll store. Prefer body when present;
        # fall back to the full content when parsing landed on an empty body.
        text = parsed.body or content.strip()
        if not text:
            report.skipped_malformed += 1
            continue

        memory_type = derive_memory_type(parsed, path.name, type_from_filename=type_from_filename)
        rule = parsed.name
        rationale = parsed.description

        # Dedup key folds metadata in — two files with identical body but
        # different rule/rationale/type are preserved (audit #7).
        key = _idempotency_key(text, rule, rationale, memory_type)
        if key in existing_keys:
            report.skipped_duplicate += 1
            continue

        # source = relative path from src_dir, optionally prefixed.
        rel = path.relative_to(src_dir).as_posix()
        source = f"{source_prefix}{rel}" if source_prefix else rel

        if dry_run:
            report.imported += 1
            report.new_ids.append(f"dry-{report.imported:04d}-{path.name}")
            existing_keys.add(key)
            continue

        new_id = remember(
            graph,
            text,
            memory_type=memory_type,
            tags=list(tags or []),
            source=source,
            rule=rule,
            rationale=rationale,
        )
        report.imported += 1
        report.new_ids.append(new_id)
        existing_keys.add(key)

        # Periodic checkpoint — flushes partial progress to disk so a
        # Ctrl-C mid-walk doesn't lose everything (audit #9). save_graph
        # is atomic, so interruption of the checkpoint itself is safe.
        since_checkpoint += 1
        if not dry_run and checkpoint_every > 0 and since_checkpoint >= checkpoint_every:
            save_graph(out_path, graph)
            since_checkpoint = 0

    if not dry_run and report.imported > 0 and since_checkpoint > 0:
        save_graph(out_path, graph)

    return report


def _collect_existing_keys(graph: Dict[str, Any]) -> set:
    """Return the set of idempotency keys already present in the graph (audit #7)."""
    keys = set()
    for n in graph.get("nodes", []):
        if n.get("id") == "memory-root":
            continue
        if n.get("parent_id") != "memory-root":
            continue
        props = n.get("properties", {})
        text = props.get("text", "")
        if not text:
            continue
        keys.add(_idempotency_key(
            text=text,
            rule=props.get("rule"),
            rationale=props.get("rationale"),
            memory_type=props.get("memory_type", ""),
        ))
    return keys


def _make_ephemeral_graph() -> Dict[str, Any]:
    """Build an in-memory graph for dry runs without touching disk."""
    return {
        "name": "LLM Memory (dry run)",
        "version": "1.0.0",
        "type": "MEMORY",
        "description": "Ephemeral memory graph for dry-run imports.",
        "dimensions": {"memory": {"description": "m", "base_level": "BASE"}},
        "capabilities": {"extensions": [], "vocabularies": ["core_v1.0.0"], "profiles": []},
        "nodes": [
            {
                "id": "memory-root",
                "type": "MODULE",
                "properties": {"name": "Memory Store"},
                "parent_id": None,
                "contains": [],
                "metric_level": "KILO_STORE",
                "dimension": "memory",
            }
        ],
        "edges": [],
    }


# ─── CLI ───────────────────────────────────────────────────────────────────────


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main() -> None:
    """CLI entry: `trugs-memory-import <src_dir> <out.trug.json> [flags]`."""
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if len(argv) < 2:
        print(
            "Usage: memory_import.py <src_dir> <out.trug.json> "
            "[--type-from-filename] [--tag TAG] [--source-prefix PREFIX] [--dry-run]",
            file=sys.stderr,
        )
        sys.exit(2)

    src_dir = Path(argv[0])
    out_path = Path(argv[1])
    type_from_filename = False
    tags: List[str] = []
    source_prefix: Optional[str] = None
    dry_run = False

    i = 2
    while i < len(argv):
        flag = argv[i]
        if flag == "--type-from-filename":
            type_from_filename = True
            i += 1
        elif flag == "--tag" and i + 1 < len(argv):
            tags.append(argv[i + 1])
            i += 2
        elif flag == "--source-prefix" and i + 1 < len(argv):
            source_prefix = argv[i + 1]
            i += 2
        elif flag == "--dry-run":
            dry_run = True
            i += 1
        else:
            print(f"Error: unknown argument '{flag}'", file=sys.stderr)
            sys.exit(2)

    try:
        report = import_flat_directory(
            src_dir,
            out_path,
            type_from_filename=type_from_filename,
            tags=tags,
            source_prefix=source_prefix,
            dry_run=dry_run,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    prefix = "[DRY RUN] " if dry_run else ""
    print(
        f"{prefix}Scanned {report.files_scanned} files. "
        f"Imported {report.imported}. "
        f"Skipped {report.skipped_duplicate} duplicate, "
        f"{report.skipped_malformed} malformed."
    )
    if dry_run:
        print(f"(No changes written to {out_path})")
    sys.exit(0)


if __name__ == "__main__":
    main()
