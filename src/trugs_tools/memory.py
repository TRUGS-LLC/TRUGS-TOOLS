"""TRUGS Memory — LLM-native persistent memory as a TRUG graph.

Memories are nodes. Associations are edges. The graph validates against CORE.

Usage:
    trugs-memory init <file>
    trugs-memory remember <file> "memory text" [flags]
    trugs-memory recall <file> [flags]
    trugs-memory forget <file> <memory_id>
    trugs-memory associate <file> <from_id> <to_id> [--relation RELATION]
    trugs-memory render <in.trug.json> <out.md> [flags]

Run `trugs-memory <command> --help` for per-command help.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Graph Operations ──────────────────────────────────────────────────────────

# PROCESS loader SHALL READ FILE graph THEN RETURN RECORD graph.
def load_graph(path: Path) -> Dict[str, Any]:
    try:
        from trugs_store import JsonFilePersistence
        store = JsonFilePersistence().load(str(path))
        graph: Dict[str, Any] = dict(store.get_metadata())
        graph["nodes"] = store.find_nodes()
        graph["edges"] = store.get_edges()
        return graph
    except ImportError:
        # Fallback: raw JSON load if trugs-store not installed
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# PROCESS saver SHALL WRITE RECORD graph TO FILE path.
def save_graph(path: Path, graph: Dict[str, Any]) -> None:
    """Atomically and durably write `graph` to `path`.

    Durability chain:
      1. Write to a sibling temp file (same directory → same filesystem).
      2. `f.flush()` + `os.fsync(f.fileno())` — content reaches stable storage.
      3. `os.replace(tmp, path)` — atomic rename on POSIX.
      4. `os.fsync(dir_fd)` on the parent directory — durably commits the
         rename metadata. Without this, on ext4/xfs a power loss immediately
         after `os.replace` can lose the rename and the file reverts to the
         old inode (audit round 3 R3-2).

    Mode preservation: if `path` already exists, the target mode is copied
    onto the tempfile so a save doesn't silently tighten permissions from
    0o644 → 0o600 (the mkstemp default). Audit round 3 R3-3.

    Cleans up the tempfile on any exception (including KeyboardInterrupt).
    """
    path = Path(os.path.realpath(path))  # M1: resolve symlinks before atomic write
    path.parent.mkdir(parents=True, exist_ok=True)

    # Capture existing mode (if any) so we can preserve it after replace.
    # Use 0o7777 (not 0o777) to preserve setgid/setuid/sticky bits — some
    # team setups use a setgid directory so created files inherit group
    # ownership, and stripping the bit every save would break that
    # (audit round 4 LOW).
    existing_mode: Optional[int] = None
    try:
        existing_mode = path.stat().st_mode & 0o7777
    except FileNotFoundError:
        existing_mode = None

    # tempfile in the same directory so os.replace is atomic on the same FS.
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        if existing_mode is not None:
            # Restore mode BEFORE os.replace so readers don't race on a
            # transient 0o600 file.
            os.chmod(tmp_path, existing_mode)
        else:
            # Honor umask for a brand-new file.
            try:
                umask = os.umask(0)
                os.umask(umask)
                os.chmod(tmp_path, 0o666 & ~umask)
            except OSError:
                pass

        os.replace(tmp_path, path)

        # Directory fsync — durably commits the rename metadata.
        # Not supported on Windows; skip with a best-effort guard.
        try:
            dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except (OSError, AttributeError):
            # Non-POSIX filesystems (Windows) or unusual mounts — fall through.
            pass
    except BaseException:
        # On any failure (including KeyboardInterrupt), clean up the temp file.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


MEMORY_GRAPH_VERSION = "1.2.0"


# PROCESS init SHALL DEFINE RECORD graph THEN WRITE RESULT TO FILE path.
def init_memory_graph(path: Path) -> Dict[str, Any]:
    """Create a new empty memory TRUG."""
    graph = {
        "name": "LLM Memory",
        "version": MEMORY_GRAPH_VERSION,
        "type": "MEMORY",
        "description": "Persistent memory graph for LLM sessions. Memories are nodes, associations are edges.",
        "dimensions": {
            "memory": {
                "description": "Memory hierarchy: store > topic > memory",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["core_v1.0.0"],
            "profiles": []
        },
        "nodes": [
            {
                "id": "memory-root",
                "type": "MODULE",
                "properties": {
                    "name": "Memory Store",
                    "created": datetime.now(timezone.utc).isoformat()
                },
                "parent_id": None,
                "contains": [],
                "metric_level": "KILO_STORE",
                "dimension": "memory"
            }
        ],
        "edges": []
    }
    save_graph(path, graph)
    return graph


# ─── Remember ──────────────────────────────────────────────────────────────────

# PROCESS remember SHALL WRITE RECORD memory TO RECORD graph.
def remember(
    graph: Dict[str, Any],
    text: str,
    memory_type: str = "FACT",
    tags: Optional[List[str]] = None,
    source: Optional[str] = None,
    *,
    rule: Optional[str] = None,
    rationale: Optional[str] = None,
    valid_to: Optional[str] = None,
    session_id: Optional[str] = None,
    supersede: Optional[str] = None,
    ref: Optional[List[str]] = None,
) -> str:
    """Add a memory node to the graph. Returns the new memory ID.

    Args:
        graph: the memory TRUG (mutated in place).
        text: full-prose memory content. Always stored.
        memory_type: canonical type. Common values: `user`, `feedback`,
            `project`, `reference`. Unknown values are accepted.
        tags: list of free-form tags for retrieval.
        source: optional URL or path citation.

    Keyword-only args (added in trugs 1.1.0):
        rule: terse executable form of the memory. If set, renderers
            prefer this over `text`. Keep under ~140 chars.
        rationale: explanatory prose — the "why" behind a rule. Not
            rendered to MEMORY.md by default (agents don't need it in
            their session context).
        valid_to: ISO-8601 timestamp at which this memory stops being
            active. Renderers filter out expired memories. `None` means
            still active.
        session_id: identifier of the session that wrote this memory.
            Enables session-scoped recall and temporal reasoning.
        supersede: id of an older memory that this one replaces. If the
            old memory's chain is already several steps deep, this new
            memory is linked to the TAIL of the chain (preserving the
            full history). `SUPERSEDES` edge + `valid_to` are applied
            to the tail; the new memory itself is never closed.
        ref: list of memory IDs that this new memory references. Creates
            a ``REFERENCES`` edge from the new memory to each target.
            Missing targets are silently skipped (warn on stderr from CLI).
            Phase 2: organic edge creation at write time — memories
            accumulate structural edges gradually instead of in batch.

    Raises:
        SupersedeError: if `supersede` is set but the target is missing,
            points at self, or the chain contains a cycle. The graph is
            left unchanged in every failure path (no orphan new memory).
    """
    memory_id = f"mem-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    # Validate supersede BEFORE mutating the graph (audit round 3 R3-1):
    # raising on a missing target previously let the CLI silently claim
    # supersede success. Now we fail loud at the library layer.
    supersede_tail: Optional[Dict[str, Any]] = None
    if supersede is not None:
        if supersede == memory_id:  # defensive; new_id is freshly generated
            raise SupersedeError(f"cannot supersede a memory with itself: {supersede}")
        old = _find_node(graph, supersede)
        if old is None:
            raise SupersedeError(f"supersede target not found: {supersede}")
        supersede_tail = _resolve_supersede_tail(graph, supersede)
        if supersede_tail is None:
            raise SupersedeError(
                f"supersede chain starting at {supersede} contains a cycle"
            )
        if supersede_tail["id"] == memory_id:
            # Impossible in practice (new_id is fresh) but cheap to assert.
            raise SupersedeError(
                f"supersede chain starting at {supersede} already terminates at {memory_id}"
            )

    props: Dict[str, Any] = {
        "text": text,
        "memory_type": memory_type,
        "created": now,
        "tags": tags or [],
    }
    if source is not None:
        props["source"] = source
    if rule is not None:
        props["rule"] = rule
    if rationale is not None:
        props["rationale"] = rationale
    if valid_to is not None:
        props["valid_to"] = valid_to
    if session_id is not None:
        props["session_id"] = session_id

    node = {
        "id": memory_id,
        "type": "DATA",
        "properties": props,
        "parent_id": "memory-root",
        "contains": [],
        "metric_level": "BASE_MEMORY",
        "dimension": "memory",
    }

    graph["nodes"].append(node)

    # Update root contains[]
    root = _find_node(graph, "memory-root")
    if root and memory_id not in root.get("contains", []):
        root["contains"].append(memory_id)

    # Apply supersede via the shared helper (audit round 3 R3-4 — eliminates
    # the duplicate inline implementation that used to live here).
    if supersede is not None:
        _apply_supersede_to_tail(graph, new_id=memory_id, tail=supersede_tail, now=now)

    # Phase 2: organic REFERENCES edges via --ref.
    if ref:
        for ref_id in ref:
            if _find_node(graph, ref_id) is not None:
                graph.setdefault("edges", []).append({
                    "from_id": memory_id,
                    "to_id": ref_id,
                    "relation": "REFERENCES",
                })

    return memory_id


# AGENT claude SHALL DEFINE RECORD supersede_error AS A RECORD exception.
class SupersedeError(Exception):
    """Raised when a supersede call violates the bi-temporal invariant.

    Subclasses `Exception` (not `ValueError`) so callers that catch
    `ValueError` for unrelated input validation don't accidentally
    swallow supersede violations (audit round 3 R3-12).
    """


def _resolve_supersede_tail(graph: Dict[str, Any], start_id: str) -> Optional[Dict[str, Any]]:
    """Walk `superseded_by` links from `start_id` until we hit a node that
    is not yet superseded, a cycle, or a missing link.

    Returns the tail node (the one currently active in the chain), or None
    if the start doesn't exist. Cycles return None rather than looping.
    """
    visited = set()
    current = _find_node(graph, start_id)
    while current is not None:
        cid = current.get("id")
        if cid in visited:
            return None  # cycle guard
        visited.add(cid)
        props = current.get("properties", {})
        successor_id = props.get("superseded_by")
        if not successor_id:
            return current
        successor = _find_node(graph, successor_id)
        if successor is None:
            return current  # dangling successor pointer — treat as tail
        current = successor
    return None


def _apply_supersede_to_tail(
    graph: Dict[str, Any],
    *,
    new_id: str,
    tail: Dict[str, Any],
    now: str,
) -> None:
    """Mutating step of the supersede workflow.

    Writes `valid_to`/`superseded_by` on the TAIL node and adds a
    `SUPERSEDES` edge from `new_id` → tail. Validation must happen
    BEFORE calling this (see `remember()` and `_apply_supersede()`),
    because this function does not raise on missing tails.

    NOTE (audit round 4 INFO): `remember()` looks up `tail` BEFORE the new
    node is appended to `graph["nodes"]` and passes the dict reference
    through here. This works because `_find_node` returns the dict by
    identity, not by index, so the reference remains valid even after
    a subsequent append. If anyone ever rewrites `_find_node` to return
    a copy, this code path will silently stop mutating the real node.
    Contract: `_find_node` returns the stored dict, period.
    """
    tail_id = tail["id"]
    props = tail.setdefault("properties", {})
    if "valid_to" not in props or props["valid_to"] is None:
        props["valid_to"] = now
    props["superseded_by"] = new_id
    associate(graph, new_id, tail_id, relation="SUPERSEDES")


def _apply_supersede(
    graph: Dict[str, Any],
    *,
    new_id: str,
    old_id: str,
    now: str,
) -> bool:
    """Close an old memory and link the new one. Returns True on success.

    Raises `SupersedeError` when:
      - `new_id == old_id` (self-supersede)
      - the chain from `old_id` contains a cycle
      - the chain from `old_id` already terminates at `new_id`

    When `old_id` is ALREADY superseded by some other node (chain exists),
    the new memory is linked to the TAIL of the chain — i.e. supersede
    `old_id` behaves as supersede the currently-active-replacement of
    `old_id`. This preserves chain-of-custody instead of silently
    orphaning middle nodes.

    Returns False if the old node doesn't exist (no raise, for direct
    test callers that want to assert non-existence without catching).
    Note: `remember(supersede=missing)` DOES raise — only this lower-
    level helper preserves the legacy False-return contract.
    """
    if new_id == old_id:
        raise SupersedeError(f"cannot supersede a memory with itself: {old_id}")

    old = _find_node(graph, old_id)
    if old is None:
        return False

    # Walk the chain to the current tail. If the chain is already terminal
    # (old_id has no superseded_by), tail == old, and we close old directly.
    tail = _resolve_supersede_tail(graph, old_id)
    if tail is None:
        # Cycle in the existing chain — refuse rather than make it worse.
        raise SupersedeError(f"supersede chain starting at {old_id} contains a cycle")

    if tail["id"] == new_id:
        raise SupersedeError(
            f"supersede chain starting at {old_id} already terminates at {new_id}"
        )

    _apply_supersede_to_tail(graph, new_id=new_id, tail=tail, now=now)
    return True


# ─── Recall ────────────────────────────────────────────────────────────────────

# PROCESS recall SHALL FILTER ALL RECORD memory THEN RETURN RECORD result.
def recall(
    graph: Dict[str, Any],
    query: Optional[str] = None,
    memory_type: Optional[str] = None,
    recent: Optional[int] = None,
    all_memories: bool = False,
    *,
    active_only: bool = False,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Query memories. Returns matching memory nodes.

    Args:
        graph: the memory TRUG.
        query: case-insensitive substring match against text, tags, or type.
        memory_type: exact match on `memory_type` (case-insensitive).
        recent: limit to N most recent results.
        all_memories: if True, skip the query/type filters but still respect
            `active_only` and `recent`.

    Keyword-only args (added in trugs 1.1.0):
        active_only: if True, exclude memories whose `valid_to` is in the past.
        now: reference timestamp for `active_only` filtering. Defaults to UTC now.
    """
    memories = [
        n for n in graph.get("nodes", [])
        if n.get("id") != "memory-root" and n.get("parent_id") == "memory-root"
    ]

    if active_only:
        ref = now or datetime.now(timezone.utc)
        memories = [m for m in memories if not _is_expired(m, ref)]

    if not all_memories:
        if query:
            q = query.lower()
            memories = [
                m for m in memories
                if q in m.get("properties", {}).get("text", "").lower()
                or q in m.get("properties", {}).get("rule", "").lower()
                or q in str(m.get("properties", {}).get("tags", [])).lower()
                or q in m.get("properties", {}).get("memory_type", "").lower()
            ]

        if memory_type:
            memories = [
                m for m in memories
                if m.get("properties", {}).get("memory_type", "").upper() == memory_type.upper()
            ]

    # Sort by created date, newest first
    memories.sort(
        key=lambda m: m.get("properties", {}).get("created", ""),
        reverse=True
    )

    if recent:
        memories = memories[:recent]

    return memories


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp with fail-open semantics.

    - None, empty string, or non-string → None
    - Malformed string → None
    - Naive (tz-less) timestamps → assumed UTC

    Shared between `_is_expired` here and `_is_past` in memory_render.py
    to prevent the two from drifting.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_expired(memory: Dict[str, Any], now: datetime) -> bool:
    """Return True if the memory's `valid_to` is strictly before `now`."""
    parsed = _parse_iso_utc(memory.get("properties", {}).get("valid_to"))
    if parsed is None:
        return False  # Fail-open: malformed timestamps are treated as active.
    return parsed < now


# ─── Forget ────────────────────────────────────────────────────────────────────

# PROCESS forget SHALL REJECT RECORD memory FROM RECORD graph.
def forget(graph: Dict[str, Any], memory_id: str) -> bool:
    """Remove a memory node and all its edges. Returns True if found."""
    node = _find_node(graph, memory_id)
    if not node:
        return False

    # Remove from parent's contains[]
    parent_id = node.get("parent_id")
    if parent_id:
        parent = _find_node(graph, parent_id)
        if parent:
            contains = parent.get("contains", [])
            if memory_id in contains:
                contains.remove(memory_id)

    # Remove all connected edges
    graph["edges"] = [
        e for e in graph.get("edges", [])
        if e.get("from_id") != memory_id and e.get("to_id") != memory_id
    ]

    # Remove the node
    graph["nodes"] = [n for n in graph["nodes"] if n.get("id") != memory_id]

    return True


# ─── Associate ─────────────────────────────────────────────────────────────────

# PROCESS associate SHALL WRITE RECORD edge TO RECORD graph.
def associate(
    graph: Dict[str, Any],
    from_id: str,
    to_id: str,
    relation: str = "REFERENCES",
) -> bool:
    """Create an edge between two memories. Returns True if both nodes exist."""
    if not _find_node(graph, from_id) or not _find_node(graph, to_id):
        return False

    # Check for duplicate
    for e in graph.get("edges", []):
        if e.get("from_id") == from_id and e.get("to_id") == to_id and e.get("relation") == relation:
            return True  # Already exists

    graph["edges"].append({
        "from_id": from_id,
        "to_id": to_id,
        "relation": relation,
    })
    return True


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _find_node(graph: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    for n in graph.get("nodes", []):
        if n.get("id") == node_id:
            return n
    return None


def _format_memory(mem: Dict[str, Any], edges: List[Dict[str, Any]]) -> str:
    """Format a memory for CLI display. Prefers `rule` over `text` if present."""
    props = mem.get("properties", {})
    body = props.get("rule") or props.get("text") or ""
    lines = [
        f"  [{mem['id']}] {props.get('memory_type', '?')}",
        f"    {body}",
    ]
    if props.get("tags"):
        lines.append(f"    tags: {', '.join(props['tags'])}")
    if props.get("source"):
        lines.append(f"    source: {props['source']}")
    lines.append(f"    created: {props.get('created', '?')}")
    if props.get("valid_to"):
        lines.append(f"    valid_to: {props['valid_to']}")
    if props.get("superseded_by"):
        lines.append(f"    superseded_by: {props['superseded_by']}")

    # Show associations
    related = [e for e in edges if e.get("from_id") == mem["id"] or e.get("to_id") == mem["id"]]
    if related:
        for e in related:
            other = e["to_id"] if e["from_id"] == mem["id"] else e["from_id"]
            direction = "→" if e["from_id"] == mem["id"] else "←"
            lines.append(f"    {direction} {e['relation']} {other}")

    return "\n".join(lines)


# ─── CLI (argparse) ────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="trugs-memory",
        description=(
            "TRUGS Memory — LLM-native persistent memory as a TRUG graph. "
            "Memories are nodes, associations are edges, the graph validates against CORE."
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = False  # Printed in main() if missing, so we can show the helpful message.

    # init
    p_init = sub.add_parser("init", help="Create an empty memory graph.")
    p_init.add_argument("file", help="Path to the new memory graph file.")

    # remember
    p_rem = sub.add_parser(
        "remember",
        help="Add a memory to the graph.",
        epilog=(
            "If the memory text begins with `-`, pass `--` first: "
            "`trugs-memory remember mem.json -- '--foo is a rule'`."
        ),
    )
    p_rem.add_argument("file", help="Path to an existing memory graph.")
    p_rem.add_argument("text", help="The memory content as prose.")
    p_rem.add_argument("--type", dest="memory_type", default="FACT",
                       help="Memory type (e.g. user, feedback, project, reference). Default: FACT")
    p_rem.add_argument("--tag", dest="tag_list", action="append", default=[],
                       help="Tag to attach to this memory. May be given multiple times. "
                            "Tags can contain commas when set via --tag (preferred).")
    p_rem.add_argument("--tags", default="",
                       help="Comma-separated tags (legacy form; use --tag for commas inside a tag).")
    p_rem.add_argument("--source", default=None, help="Optional source URL or citation.")
    p_rem.add_argument("--rule", default=None,
                       help="Terse executable form of the memory. Renderers prefer this over `text`.")
    p_rem.add_argument("--rationale", default=None,
                       help="Explanatory prose. Not rendered to MEMORY.md by default.")
    p_rem.add_argument("--valid-to", default=None,
                       help="ISO-8601 timestamp when this memory stops being active. "
                            "Must parse via datetime.fromisoformat — garbage is rejected.")
    p_rem.add_argument("--session-id", default=None,
                       help="Identifier of the session that wrote this memory.")
    p_rem.add_argument("--supersede", default=None,
                       help="ID of an older memory this one replaces. Closes the old memory "
                            "(valid_to=now, superseded_by=<new>) and adds a SUPERSEDES edge. "
                            "If the old memory is already superseded, the new memory is linked "
                            "to the tail of the existing chain, not the original.")
    p_rem.add_argument("--ref", dest="ref_ids", action="append", default=[],
                       help="ID of a memory this one references. Creates a REFERENCES edge. "
                            "May be given multiple times. Missing targets are silently skipped.")

    # recall
    p_recall = sub.add_parser("recall", help="Query memories.")
    p_recall.add_argument("file", help="Path to the memory graph.")
    p_recall.add_argument("--query", default=None,
                          help="Case-insensitive substring match across text, rule, tags, type.")
    p_recall.add_argument("--type", dest="memory_type", default=None,
                          help="Filter by memory type (exact match, case-insensitive).")
    p_recall.add_argument("--recent", type=int, default=None,
                          help="Limit to N most recent results.")
    p_recall.add_argument("--all", dest="all_memories", action="store_true",
                          help="Skip query/type filters; still respects --active-only and --recent.")
    p_recall.add_argument("--active-only", action="store_true",
                          help="Exclude memories whose valid_to is in the past.")

    # forget
    p_for = sub.add_parser("forget", help="Remove a memory and all its edges.")
    p_for.add_argument("file", help="Path to the memory graph.")
    p_for.add_argument("memory_id", help="ID of the memory to remove.")

    # associate
    p_asc = sub.add_parser("associate", help="Create an edge between two memories.")
    p_asc.add_argument("file", help="Path to the memory graph.")
    p_asc.add_argument("from_id", help="Source memory ID.")
    p_asc.add_argument("to_id", help="Target memory ID.")
    p_asc.add_argument("--relation", default="REFERENCES",
                       help="TRL preposition (e.g. REFERENCES, SUPERSEDES, GOVERNS, "
                            "DEPENDS_ON, CONTAINS). Default: REFERENCES")

    # render (delegates to memory_render)
    p_ren = sub.add_parser("render", help="Render the memory graph to a markdown file.")
    p_ren.add_argument("in_file", metavar="in.trug.json", help="Path to the memory graph.")
    p_ren.add_argument("out_file", metavar="out.md", help="Path to the rendered markdown output.")
    p_ren.add_argument("--budget", type=int, default=8000,
                       help="Soft token budget for the rendered output. Default: 8000")
    p_ren.add_argument("--include-rationale", action="store_true",
                       help="Include rationale text in the rendered output.")

    # import-flat (delegates to memory_import)
    p_imp = sub.add_parser("import-flat", help="Bulk import flat markdown files into a memory graph.")
    p_imp.add_argument("src_dir", help="Directory of markdown files to walk (recursive).")
    p_imp.add_argument("out_file", metavar="out.trug.json", help="Target memory graph (created if missing).")
    p_imp.add_argument("--type-from-filename", action="store_true",
                       help="Derive memory_type from filename prefix when frontmatter lacks a type field.")
    p_imp.add_argument("--tag", dest="tags", action="append", default=[],
                       help="Tag to apply to every imported memory. May be given multiple times.")
    p_imp.add_argument("--source-prefix", default=None,
                       help="String prepended to each memory's source property.")
    p_imp.add_argument("--dry-run", action="store_true",
                       help="Scan and report without writing.")

    # audit (delegates to memory_audit)
    p_aud = sub.add_parser("audit", help="Dead-rule report and hit-count instrumentation.")
    p_aud.add_argument("file", help="Path to the memory graph.")
    p_aud.add_argument("--dead-rules", dest="dead_rules_spec", default=None,
                       help="Duration threshold (e.g. 30d, 2w, 1m, 1y).")
    p_aud.add_argument("--bump", dest="bump_id", default=None,
                       help="Increment hit_count and update last_hit for the given memory ID.")

    # reconcile (delegates to memory_audit)
    p_reconcile = sub.add_parser("reconcile", help="Detect duplicate-candidate memory pairs.")
    p_reconcile.add_argument("file", help="Path to the memory graph.")
    p_reconcile.add_argument("--threshold", type=float, default=0.7,
                             help="Jaccard similarity cutoff in [0.0, 1.0]. Default: 0.7")
    p_reconcile.add_argument("--type", dest="memory_type", default=None,
                             help="Only compare memories of this type.")

    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if path.exists():
        print(f"Error: {path} already exists", file=sys.stderr)
        return 1
    init_memory_graph(path)
    print(f"Created memory graph: {path}")
    return 0


def _cmd_remember(args: argparse.Namespace) -> int:
    path = Path(args.file)

    # Merge --tag (repeatable) and --tags (legacy comma form).
    tags: List[str] = list(getattr(args, "tag_list", []))
    if args.tags:
        tags.extend(t.strip() for t in args.tags.split(",") if t.strip())

    # Validate --valid-to as ISO-8601 before writing. Fail-loud at the CLI
    # boundary so a fat-finger doesn't silently store a garbage timestamp
    # that fail-open filtering will later treat as active.
    if args.valid_to is not None:
        if _parse_iso_utc(args.valid_to) is None:
            print(
                f"Error: --valid-to must be ISO-8601 (got {args.valid_to!r}). "
                f"Example: 2026-12-31T00:00:00+00:00",
                file=sys.stderr,
            )
            return 2

    graph = load_graph(path)
    ref_ids = getattr(args, "ref_ids", []) or []

    try:
        mid = remember(
            graph,
            args.text,
            memory_type=args.memory_type,
            tags=tags,
            source=args.source,
            rule=args.rule,
            rationale=args.rationale,
            valid_to=args.valid_to,
            session_id=args.session_id,
            supersede=args.supersede,
            ref=ref_ids if ref_ids else None,
        )
    except SupersedeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    save_graph(path, graph)
    print(f"Remembered: {mid}")
    if args.supersede:
        # Report the actual node that got closed — it may differ from
        # args.supersede when the chain was walked to its tail
        # (audit round 3 R3-1 corollary: stop lying about which node
        # was touched).
        sup_edge = next(
            (e for e in graph.get("edges", [])
             if e.get("from_id") == mid and e.get("relation") == "SUPERSEDES"),
            None,
        )
        closed = sup_edge["to_id"] if sup_edge else args.supersede
        if closed == args.supersede:
            print(f"Superseded: {closed}")
        else:
            print(f"Superseded: {closed} (tail of {args.supersede})")
    # Report REFERENCES edges created by --ref.
    if ref_ids:
        ref_edges = [
            e for e in graph.get("edges", [])
            if e.get("from_id") == mid and e.get("relation") == "REFERENCES"
        ]
        for re_ in ref_edges:
            print(f"References: {re_['to_id']}")
        skipped = len(ref_ids) - len(ref_edges)
        if skipped > 0:
            print(f"  ({skipped} ref target(s) not found — skipped)", file=sys.stderr)
    return 0


def _cmd_recall(args: argparse.Namespace) -> int:
    path = Path(args.file)
    graph = load_graph(path)
    results = recall(
        graph,
        query=args.query,
        memory_type=args.memory_type,
        recent=args.recent,
        all_memories=args.all_memories,
        active_only=args.active_only,
    )
    edges = graph.get("edges", [])
    if not results:
        print("No memories found.")
    else:
        print(f"{len(results)} memories:")
        for m in results:
            print(_format_memory(m, edges))
    return 0


def _cmd_forget(args: argparse.Namespace) -> int:
    path = Path(args.file)
    graph = load_graph(path)
    if forget(graph, args.memory_id):
        save_graph(path, graph)
        print(f"Forgot: {args.memory_id}")
        return 0
    print(f"Error: memory '{args.memory_id}' not found", file=sys.stderr)
    return 1


def _cmd_associate(args: argparse.Namespace) -> int:
    path = Path(args.file)
    graph = load_graph(path)
    if associate(graph, args.from_id, args.to_id, args.relation):
        save_graph(path, graph)
        print(f"Associated: {args.from_id} --[{args.relation}]--> {args.to_id}")
        return 0
    print("Error: one or both nodes not found", file=sys.stderr)
    return 1


def _cmd_render(args: argparse.Namespace) -> int:
    try:
        from trugs_tools.memory_render import render_to_file  # test/dev cwd=tools/
    except ImportError:
        from trugs_tools.memory_render import render_to_file  # installed package
    # Use load_graph (not raw json.load) for consistency with every other
    # _cmd_* handler — any future behavior change in load_graph (schema
    # upgrade, validation) applies uniformly (audit round 3 R3-10).
    graph = load_graph(Path(args.in_file))
    n = render_to_file(
        graph,
        Path(args.out_file),
        token_budget=args.budget,
        include_rationale=args.include_rationale,
    )
    print(f"Rendered {n} bytes to {args.out_file}")
    return 0


def _cmd_import_flat(args: argparse.Namespace) -> int:
    try:
        from trugs_tools.memory_import import import_flat_directory  # test/dev cwd=tools/
    except ImportError:
        from trugs_tools.memory_import import import_flat_directory  # installed package
    try:
        report = import_flat_directory(
            Path(args.src_dir),
            Path(args.out_file),
            type_from_filename=args.type_from_filename,
            tags=args.tags,
            source_prefix=args.source_prefix,
            dry_run=args.dry_run,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    prefix = "[DRY RUN] " if args.dry_run else ""
    print(
        f"{prefix}Scanned {report.files_scanned} files. "
        f"Imported {report.imported}. "
        f"Skipped {report.skipped_duplicate} duplicate, "
        f"{report.skipped_malformed} malformed, "
        f"{report.skipped_outside} symlink-escape."
    )
    if args.dry_run:
        print(f"(No changes written to {args.out_file})")
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    try:
        from trugs_tools.memory_audit import _main_audit  # test/dev cwd=tools/
    except ImportError:
        from trugs_tools.memory_audit import _main_audit  # installed package
    forwarded: List[str] = [args.file]
    if args.dead_rules_spec is not None:
        forwarded += ["--dead-rules", args.dead_rules_spec]
    if args.bump_id is not None:
        forwarded += ["--bump", args.bump_id]
    return _main_audit(forwarded)


def _cmd_reconcile(args: argparse.Namespace) -> int:
    try:
        from trugs_tools.memory_audit import _main_reconcile  # test/dev cwd=tools/
    except ImportError:
        from trugs_tools.memory_audit import _main_reconcile  # installed package
    forwarded: List[str] = [args.file, "--threshold", str(args.threshold)]
    if args.memory_type is not None:
        forwarded += ["--type", args.memory_type]
    return _main_reconcile(forwarded)


_COMMANDS = {
    "init": _cmd_init,
    "remember": _cmd_remember,
    "recall": _cmd_recall,
    "forget": _cmd_forget,
    "associate": _cmd_associate,
    "render": _cmd_render,
    "import-flat": _cmd_import_flat,
    "audit": _cmd_audit,
    "reconcile": _cmd_reconcile,
}


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.error(f"Unknown command: {args.command}")
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
