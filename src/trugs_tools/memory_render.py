"""TRUGS Memory Render — deterministic markdown render of a memory TRUG.

Reads a memory graph produced by `trugs-memory` and emits a single
integrated `MEMORY.md` file that an LLM agent can load at session start.

The renderer is:
  - Deterministic: same graph in → same bytes out.
  - Temporal-aware: filters nodes whose `valid_to` is in the past.
  - Grouped by `memory_type` with a stable default order.
  - Budget-aware: if the rendered output exceeds the token budget, the
    oldest `project` entries are demoted first, then `reference`.
    `user` and `feedback` entries are never demoted (they are the
    behavioral rules Claude needs every session).

Usage:
    python tools/memory_render.py <in.trug.json> <out.md> [--budget N] [--include-rationale]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─── Public API ────────────────────────────────────────────────────────────────

#: Default order for `memory_type` sections in the rendered output.
DEFAULT_TYPE_ORDER: Tuple[str, ...] = ("user", "feedback", "project", "reference")

#: Default render budget (approximate tokens). 1 token ≈ 4 characters is a
#: standard rule of thumb for English; we use that here as a conservative
#: bound. Callers can override with any integer.
DEFAULT_BUDGET_TOKENS: int = 8000

#: Order in which sections get demoted when over budget. `user` and
#: `feedback` are never demoted — they are behavioral load-bearing.
DEMOTION_ORDER: Tuple[str, ...] = ("project", "reference")


# PROCESS render SHALL MAP RECORD graph TO STRING DATA output.
def render(
    graph: Dict[str, Any],
    *,
    token_budget: int = DEFAULT_BUDGET_TOKENS,
    include_rationale: bool = False,
    now: Optional[datetime] = None,
    type_order: Tuple[str, ...] = DEFAULT_TYPE_ORDER,
) -> str:
    """Render a memory graph to a single markdown string.

    Args:
        graph: a memory TRUG dict (as produced by `tools.memory.init_memory_graph`).
        token_budget: soft upper bound on rendered output, in approximate tokens
            (4 chars ≈ 1 token). Sections are demoted when over budget.
        include_rationale: if True, each memory's `rationale` property is
            emitted as a quoted sub-block. Default False (Claude only needs rules).
        now: reference timestamp for `valid_to` filtering. Defaults to UTC now.
        type_order: tuple of `memory_type` section names in the order they
            should appear. Unknown types are appended at the end, sorted.

    Returns:
        The rendered markdown, terminating with a single trailing newline.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    active = _active_memories(graph, now=now)
    grouped = _group_by_type(active, type_order=type_order)

    header_lines = _render_header(graph, grouped, now=now)
    body = _render_body(grouped, include_rationale=include_rationale)

    # Budget enforcement — demote oldest entries in DEMOTION_ORDER types.
    final_body = _apply_budget(
        header_lines,
        body,
        grouped,
        token_budget=token_budget,
        include_rationale=include_rationale,
    )

    out = "\n".join(header_lines) + "\n\n" + final_body
    if not out.endswith("\n"):
        out += "\n"
    return out


# PROCESS render SHALL MAP RECORD graph TO FILE output.
def render_to_file(
    graph: Dict[str, Any],
    path: Path,
    **kwargs: Any,
) -> int:
    """Render `graph` to `path`. Returns the number of bytes written.

    Keyword arguments are forwarded to `render()`.
    """
    text = render(graph, **kwargs)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return len(text.encode("utf-8"))


# ─── Internals ─────────────────────────────────────────────────────────────────


_PROJECT_DECAY_DAYS: int = 7
"""Project memories older than this with zero non-CONTAINS edges are
excluded from rendering. They remain on disk for ``recall --query``.
The edge count acts as a graduation mechanism: a project memory that
earns a REFERENCES or DEPENDS_ON edge survives past the decay window."""


def _edge_count(graph: Dict[str, Any], node_id: str) -> int:
    """Count non-CONTAINS edges touching ``node_id``."""
    count = 0
    for e in graph.get("edges", []):
        if e.get("relation") == "CONTAINS":
            continue
        if e.get("from_id") == node_id or e.get("to_id") == node_id:
            count += 1
    return count


def _active_memories(
    graph: Dict[str, Any],
    *,
    now: datetime,
) -> List[Dict[str, Any]]:
    """Return memory nodes under `memory-root` that should be rendered.

    Filters:
      - ``valid_to`` in the past → excluded (expired).
      - ``memory_type == "project"`` AND older than ``_PROJECT_DECAY_DAYS``
        AND zero non-CONTAINS edges → excluded (ephemeral, decayed).
    """
    from datetime import timedelta

    memories: List[Dict[str, Any]] = []
    for n in graph.get("nodes", []):
        if n.get("id") == "memory-root":
            continue
        if n.get("parent_id") != "memory-root":
            continue
        props = n.get("properties", {})
        valid_to = props.get("valid_to")
        if valid_to and _is_past(valid_to, now=now):
            continue
        # Phase 2: decay project memories older than _PROJECT_DECAY_DAYS
        # unless they have structural edges (someone depends on them).
        mtype = (props.get("memory_type") or "").lower()
        if mtype == "project":
            created_epoch = _created_epoch(n)
            if created_epoch > 0:
                from datetime import timezone as _tz
                created_dt = datetime.fromtimestamp(created_epoch, tz=_tz.utc)
                age = now - created_dt
                if age > timedelta(days=_PROJECT_DECAY_DAYS):
                    if _edge_count(graph, n.get("id", "")) == 0:
                        continue  # ephemeral, decayed — skip render
        memories.append(n)
    return memories


def _is_past(iso_timestamp: Any, *, now: datetime) -> bool:
    """Return True if the given ISO-8601 timestamp is strictly before `now`.

    Delegates to `memory._parse_iso_utc` so this function and `memory._is_expired`
    share a single source of timestamp-parsing truth (audit round 2 #14).
    """
    try:
        from trugs_tools.memory import _parse_iso_utc  # test/dev cwd=tools/
    except ImportError:
        from trugs_tools.memory import _parse_iso_utc  # installed package
    parsed = _parse_iso_utc(iso_timestamp)
    if parsed is None:
        return False
    return parsed < now


def _group_by_type(
    memories: List[Dict[str, Any]],
    *,
    type_order: Tuple[str, ...],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group memories by `properties.memory_type`, ordered by type_order.

    Within each group, memories are sorted by `properties.created` descending
    (newest first). Unknown memory_types are appended at the end in sorted
    order for determinism.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for m in memories:
        t = (m.get("properties", {}).get("memory_type") or "other").lower()
        buckets.setdefault(t, []).append(m)

    # Sort each bucket: newest first, stable on id for determinism.
    for t, lst in buckets.items():
        lst.sort(
            key=lambda m: (
                -_created_epoch(m),
                m.get("id", ""),
            )
        )

    # Rebuild in deterministic order: known types first in given order,
    # then unknown types sorted alphabetically.
    ordered: Dict[str, List[Dict[str, Any]]] = {}
    for t in type_order:
        if t in buckets:
            ordered[t] = buckets.pop(t)
    for t in sorted(buckets):
        ordered[t] = buckets[t]
    return ordered


def _created_epoch(memory: Dict[str, Any]) -> float:
    """Return `created` as a float epoch for sort ordering. Missing → 0."""
    created = memory.get("properties", {}).get("created", "")
    try:
        dt = datetime.fromisoformat(created)
    except (TypeError, ValueError):
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _graph_high_water_mark(graph: Dict[str, Any]) -> Optional[str]:
    """Return the latest ISO timestamp found in any memory node's `created` or
    `valid_to` property, or None if the graph has no temporal data.

    Used as the deterministic stand-in for "when was this rendered" — the
    header timestamp must be a function of the graph alone, not wall-clock,
    or two runs against the same graph produce different bytes (round-5
    audit finding C-H4).
    """
    latest: Optional[str] = None
    for n in graph.get("nodes", []):
        if n.get("parent_id") != "memory-root":
            continue
        props = n.get("properties", {})
        for key in ("created", "valid_to"):
            ts = props.get(key)
            if not ts or not isinstance(ts, str):
                continue
            if latest is None or ts > latest:
                latest = ts
    return latest


def _render_header(
    graph: Dict[str, Any],
    grouped: Dict[str, List[Dict[str, Any]]],
    *,
    now: datetime,  # kept for API compatibility; no longer rendered
) -> List[str]:
    """Render the top-of-file metadata block as a list of lines.

    The header is byte-deterministic: it depends only on the graph
    contents, not on wall-clock time. The "rendered at" anchor is the
    high-water mark of `created` / `valid_to` across all memory nodes
    (i.e. the most recent write to the graph), which changes only when
    the graph itself changes.
    """
    del now  # unused — kept in signature for callers that pass it
    total = sum(len(v) for v in grouped.values())
    counts = ", ".join(f"{t}={len(v)}" for t, v in grouped.items() if v)
    high_water = _graph_high_water_mark(graph)
    if high_water:
        anchor_line = (
            f"> Rendered from `{graph.get('name', 'memory graph')}`. "
            f"Latest write at {high_water}."
        )
    else:
        anchor_line = (
            f"> Rendered from `{graph.get('name', 'memory graph')}`."
        )
    return [
        f"# MEMORY",
        "",
        anchor_line,
        f"> {total} active memories — {counts if counts else '(none)'}.",
        f"> **Do not edit.** This file is produced by `trugs-memory render`.",
    ]


def _render_body(
    grouped: Dict[str, List[Dict[str, Any]]],
    *,
    include_rationale: bool,
) -> str:
    """Render grouped memories as markdown body (type sections + entries).

    Feedback memories are sub-grouped by their first tag (Phase 2 change 2).
    This clusters 100+ flat feedback rules into scannable sections without
    restructuring the underlying graph.
    """
    chunks: List[str] = []
    for t, memories in grouped.items():
        if not memories:
            continue
        chunks.append(f"## {t}")
        chunks.append("")
        if t == "feedback" and len(memories) > 5:
            # Sub-group by first tag for scannability.
            chunks.extend(_render_feedback_grouped(memories, include_rationale=include_rationale))
        else:
            for m in memories:
                chunks.append(_render_memory(m, include_rationale=include_rationale))
                chunks.append("")
    if not chunks:
        return "_(no active memories)_\n"
    return "\n".join(chunks).rstrip() + "\n"


def _render_feedback_grouped(
    memories: List[Dict[str, Any]],
    *,
    include_rationale: bool,
) -> List[str]:
    """Sub-group feedback memories by first tag, rendering each group
    under a ``### tag (N)`` heading. Memories with no tags go under
    ``### general``. Deterministic: groups sorted alphabetically."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for m in memories:
        tags = m.get("properties", {}).get("tags") or []
        key = tags[0] if tags else "general"
        groups.setdefault(key, []).append(m)

    chunks: List[str] = []
    for group_name in sorted(groups):
        group = groups[group_name]
        chunks.append(f"### {group_name} ({len(group)})")
        chunks.append("")
        for m in group:
            chunks.append(_render_memory(m, include_rationale=include_rationale))
            chunks.append("")
    return chunks


def _render_memory(
    memory: Dict[str, Any],
    *,
    include_rationale: bool,
) -> str:
    """Render a single memory as a markdown bullet + optional rationale block."""
    props = memory.get("properties", {})
    body = props.get("rule") or props.get("text") or ""
    body = body.strip()
    # I1: collapse multi-line body to single line — memories are one-line
    # summaries in the rendered index; multi-line content belongs in rationale.
    body = body.replace("\n", " ").replace("\r", "")

    lines = [f"- {body}" if body else "- _(empty memory)_"]

    tags = props.get("tags") or []
    if tags:
        lines.append(f"  tags: {', '.join(tags)}")

    if include_rationale:
        rationale = (props.get("rationale") or "").strip()
        if rationale:
            for rl in rationale.splitlines():
                lines.append(f"  > {rl}")

    return "\n".join(lines)


def _approx_tokens(text: str) -> int:
    """Approximate token count. 1 token ≈ 4 chars (English rule of thumb).

    Empty input returns 0 (not 1) — fixes an off-by-one that inflated budgets
    by a token per empty render.
    """
    if not text:
        return 0
    return (len(text) + 3) // 4


def _estimate_memory_tokens(memory: Dict[str, Any], include_rationale: bool) -> int:
    """Rough per-memory token contribution. Used by the incremental budget loop.

    When rationale is included, the renderer prefixes every line with `  > `
    (4 chars). Naive `_approx_tokens(rationale)` undercounts by roughly one
    token per rationale line. Add a line-count correction so the pre-check
    for "protected overflow" is accurate (audit round 3 R3-5).
    """
    props = memory.get("properties", {})
    body = props.get("rule") or props.get("text") or ""
    total = _approx_tokens(body) + 4  # + bullet, newlines, tag line
    tags = props.get("tags") or []
    if tags:
        total += _approx_tokens(", ".join(tags)) + 2
    if include_rationale:
        rationale = props.get("rationale") or ""
        total += _approx_tokens(rationale)
        if rationale:
            # `  > ` prefix per line (~1 token/line).
            total += rationale.count("\n") + 1
    return total


def _apply_budget(
    header_lines: List[str],
    body: str,
    grouped: Dict[str, List[Dict[str, Any]]],
    *,
    token_budget: int,
    include_rationale: bool,
) -> str:
    """Demote oldest entries in DEMOTION_ORDER types until body fits budget.

    `user` and `feedback` are never demoted. Demoted entries are dropped from
    the output; they remain on disk in the source TRUG.

    Uses an incremental token estimate so the loop is O(n), not O(n²). If the
    protected sections (`user` + `feedback`) are already over budget on their
    own, demoting `project`/`reference` cannot help — in that case the function
    emits the full body with a warning header instead of looping uselessly.
    """
    header = "\n".join(header_lines)
    header_tokens = _approx_tokens(header) + 1  # +1 for the blank line
    budget_for_body = token_budget - header_tokens

    if token_budget <= 0:
        # Non-positive budget — emit a warning note but render everything.
        return (
            body.rstrip()
            + "\n\n_Warning: token_budget ≤ 0; ignored._\n"
        )

    if _approx_tokens(body) <= budget_for_body:
        return body

    # Pre-check: if the protected sections alone bust the budget, demotion is
    # pointless. Emit the full body with a warning so the caller sees why the
    # render is over.
    protected_tokens = 0
    for t, bucket in grouped.items():
        if t in DEMOTION_ORDER:
            continue
        for m in bucket:
            protected_tokens += _estimate_memory_tokens(m, include_rationale)

    if protected_tokens > budget_for_body:
        note = (
            "\n_Warning: protected sections (user+feedback) already exceed the "
            f"token budget ({protected_tokens} > {budget_for_body}); no demotion applied._\n"
        )
        return body.rstrip() + "\n" + note

    # Incremental demotion: compute initial body tokens, subtract per-pop
    # estimates. O(n) in the number of pops instead of O(n²) re-renders.
    working: Dict[str, List[Dict[str, Any]]] = {
        t: list(lst) for t, lst in grouped.items()
    }
    running_tokens = _approx_tokens(body)

    demoted_count = 0
    for t in DEMOTION_ORDER:
        bucket = working.get(t)
        if not bucket:
            continue
        # Pop oldest entries first (bucket is newest-first, so pop from end).
        while bucket and running_tokens > budget_for_body:
            popped = bucket.pop()
            running_tokens -= _estimate_memory_tokens(popped, include_rationale)
            demoted_count += 1
        if not bucket:
            # Remove empty bucket entirely to avoid an orphan section header.
            del working[t]
        if running_tokens <= budget_for_body:
            break

    new_body = _render_body(working, include_rationale=include_rationale)

    if demoted_count > 0:
        note = f"\n_{demoted_count} memories demoted for budget; still on disk in the graph._\n"
        new_body = new_body.rstrip() + "\n" + note
    return new_body


# ─── CLI ───────────────────────────────────────────────────────────────────────


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main() -> None:
    """CLI entry: `trugs-memory-render <in.trug.json> <out.md> [flags]`.

    Delegates to `memory._cmd_render` via the shared argparse parser in
    `memory._build_parser()` so the two entry points (`trugs-memory render`
    and `trugs-memory-render`) can't drift out of sync (audit round 2 #20).
    """
    try:
        from trugs_tools.memory import _build_parser, _cmd_render  # test/dev cwd=tools/
    except ImportError:
        from trugs_tools.memory import _build_parser, _cmd_render  # installed package

    parser = _build_parser()
    # Prepend the "render" subcommand so users running `trugs-memory-render`
    # don't have to type it — this entry point is for direct render use.
    args = parser.parse_args(["render"] + sys.argv[1:])
    sys.exit(_cmd_render(args))


if __name__ == "__main__":
    main()
