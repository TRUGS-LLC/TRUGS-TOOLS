"""TRUGS Memory Audit — usage instrumentation and reconcile-candidate detection.

Two independent concerns bundled together:

1. **Usage instrumentation** — `hit_count` and `last_hit` properties on
   each memory node, bumped by the agent whenever it explicitly cites
   the memory. `dead_rules()` surfaces feedback memories that have not
   been consulted within a threshold — the MemoryBench "is the feedback
   actually driving behavior?" check.

2. **Reconcile-candidate detection** — `reconcile_candidates()` returns
   pairs of memories with high text-similarity (token-set Jaccard).
   The tool does NOT merge — it surfaces candidates for an LLM or
   human to review. The merge decision is always external.

Usage:
    trugs-memory audit <file>              — dead-rules report + summary
    trugs-memory audit <file> --dead-rules 30d
    trugs-memory audit <file> --bump <memory_id>
    trugs-memory reconcile <file>          — print duplicate candidate pairs
    trugs-memory reconcile <file> --threshold 0.8
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from trugs_tools.memory import _find_node, load_graph, save_graph
except ImportError:
    from trugs_tools.memory import _find_node, load_graph, save_graph


# ─── Usage instrumentation ────────────────────────────────────────────────────


# PROCESS audit SHALL WRITE RECORD hit TO RECORD memory.
def bump_hit(
    graph: Dict[str, Any],
    memory_id: str,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Increment `hit_count` and update `last_hit` for the given memory.

    Returns True if the memory was found, False otherwise. Does not raise
    on missing memory. Mutates the graph in place; caller is responsible
    for persisting.
    """
    node = _find_node(graph, memory_id)
    if node is None:
        return False
    if node.get("id") == "memory-root":
        return False
    ref = now or datetime.now(timezone.utc)
    props = node.setdefault("properties", {})
    props["hit_count"] = int(props.get("hit_count", 0)) + 1
    props["last_hit"] = ref.isoformat()
    return True


# AGENT claude SHALL DEFINE RECORD dead_rule AS A RECORD finding.
@dataclass
class DeadRule:
    """A feedback memory that has not been cited within the threshold."""

    memory_id: str
    text: str
    rule: Optional[str]
    created: Optional[str]
    hit_count: int


# PROCESS audit SHALL FILTER ALL RECORD memory THEN RETURN RECORD dead_rule.
def dead_rules(
    graph: Dict[str, Any],
    *,
    older_than_days: int = 30,
    now: Optional[datetime] = None,
) -> List[DeadRule]:
    """Return feedback memories with hit_count == 0 and created > threshold.

    A "dead rule" is a feedback memory the agent has never cited. If the
    memory was written recently (within `older_than_days`) it's not yet
    dead — the agent may simply not have had a chance to use it.

    Args:
        graph: the memory TRUG.
        older_than_days: only flag memories created before this many days
            ago. Default 30.
        now: reference timestamp. Defaults to UTC now.

    Returns:
        List of DeadRule records, sorted oldest-first.
    """
    ref = now or datetime.now(timezone.utc)
    threshold = ref - timedelta(days=older_than_days)
    dead: List[DeadRule] = []

    for n in graph.get("nodes", []):
        if n.get("id") == "memory-root":
            continue
        if n.get("parent_id") != "memory-root":
            continue
        props = n.get("properties", {})
        # audit #17 — strip whitespace before comparing memory_type.
        if (props.get("memory_type", "") or "").strip().lower() != "feedback":
            continue
        if int(props.get("hit_count", 0)) > 0:
            continue
        created_str = props.get("created")
        created_dt = _parse_iso(created_str)
        if created_dt is None or created_dt >= threshold:
            # Either unparseable (leave it alone) or too recent to be dead.
            continue
        dead.append(
            DeadRule(
                memory_id=n["id"],
                text=props.get("text", ""),
                rule=props.get("rule"),
                created=created_str,
                hit_count=int(props.get("hit_count", 0)),
            )
        )

    dead.sort(key=lambda d: d.created or "")
    return dead


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp. Delegates to memory._parse_iso_utc
    so this function and `memory._is_expired` stay in lockstep
    (audit #14)."""
    try:
        from trugs_tools.memory import _parse_iso_utc  # test/dev cwd=tools/
    except ImportError:
        from trugs_tools.memory import _parse_iso_utc  # installed package
    return _parse_iso_utc(value)


# ─── Reconcile candidate detection ────────────────────────────────────────────


# AGENT claude SHALL DEFINE RECORD candidate AS A RECORD finding.
@dataclass
class ReconcileCandidate:
    """A pair of memories that may be duplicates. LLM/human decides."""

    a_id: str
    b_id: str
    a_text: str
    b_text: str
    similarity: float


DEFAULT_SIMILARITY_THRESHOLD = 0.7


# PROCESS audit SHALL FILTER ALL RECORD memory THEN RETURN RECORD candidate.
def reconcile_candidates(
    graph: Dict[str, Any],
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    memory_type: Optional[str] = None,
) -> List[ReconcileCandidate]:
    """Return pairs of memories whose token-set Jaccard similarity ≥ threshold.

    Does NOT merge, does NOT close, does NOT touch the graph. The merge
    decision is always external (LLM or human). This function's job is
    to narrow the search space for the reconciler.

    Args:
        graph: the memory TRUG.
        threshold: Jaccard similarity cutoff in [0.0, 1.0]. Default 0.7.
        memory_type: if set, only compare memories of this type (e.g.
            "feedback"). Default None = all types.

    Returns:
        List of ReconcileCandidate records, sorted by descending similarity.
        Pairs are deduplicated: (a, b) and (b, a) collapse to one entry.
    """
    memories = [
        n for n in graph.get("nodes", [])
        if n.get("id") != "memory-root" and n.get("parent_id") == "memory-root"
    ]
    if memory_type:
        memories = [
            m for m in memories
            if m.get("properties", {}).get("memory_type", "").lower() == memory_type.lower()
        ]

    # Precompute token sets once to avoid O(n²) tokenization.
    tokenized: List[Tuple[str, str, set]] = []
    for m in memories:
        text = _best_text(m)
        tokenized.append((m["id"], text, _tokenize(text)))

    # Length-ratio blocking cheap-skip: Jaccard ≤ min(|A|, |B|) / max(|A|, |B|).
    # If that upper bound < threshold, no need to compute the intersection.
    # Saves the bulk of the O(n²) comparisons when the token-set sizes differ
    # widely — common in a real memory store where a short `rule` field
    # coexists with verbose prose bodies (audit #6).
    candidates: List[ReconcileCandidate] = []
    for i in range(len(tokenized)):
        aid, atext, atokens = tokenized[i]
        if not atokens:
            continue
        a_len = len(atokens)
        for j in range(i + 1, len(tokenized)):
            bid, btext, btokens = tokenized[j]
            if not btokens:
                continue
            b_len = len(btokens)
            # Upper bound on Jaccard for these two sets.
            if min(a_len, b_len) / max(a_len, b_len) < threshold:
                continue
            sim = _jaccard(atokens, btokens)
            if sim >= threshold:
                candidates.append(
                    ReconcileCandidate(
                        a_id=aid,
                        b_id=bid,
                        a_text=atext,
                        b_text=btext,
                        similarity=sim,
                    )
                )

    candidates.sort(key=lambda c: c.similarity, reverse=True)
    return candidates


def _best_text(memory: Dict[str, Any]) -> str:
    """Return the most representative text for a memory — rule > text."""
    props = memory.get("properties", {})
    return props.get("rule") or props.get("text") or ""


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> set:
    """Lowercase alphanumeric token set for Jaccard similarity."""
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity coefficient in [0, 1]."""
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union


# ─── CLI ───────────────────────────────────────────────────────────────────────


def _parse_duration_days(spec: str) -> int:
    """Parse a duration string like '30d', '2w', '6mo' into days.

    Suffixes (case-insensitive):
      d   → days
      w   → weeks × 7
      mo  → months × 30  (audit round 3 R3-8: we require 'mo' for months,
                          not 'm', to avoid the 'minute' ambiguity from
                          systemd/timeout conventions)
      y   → years × 365

    A bare integer is interpreted as days.

    Rejects negative or zero durations (audit round 2 #4) — a `-30d`
    threshold would land in the future and flag every feedback memory as
    dead, which is worse than an error.

    Rejects a bare `m` suffix explicitly: users are likely thinking
    "minutes" (systemd style); we force them to type `mo` for months
    so the intent is unambiguous.
    """
    # L2: reject non-string inputs that would raise AttributeError
    if not isinstance(spec, str):
        raise ValueError(f"Duration must be a string, got {type(spec).__name__}")
    # L2: reject internal whitespace (e.g. "30 d" typo)
    stripped = spec.strip()
    if " " in stripped or "\t" in stripped:
        raise ValueError(f"Duration must not contain whitespace: {spec!r}")
    spec = stripped.lower()
    if not spec:
        raise ValueError("empty duration")

    # Longest suffix first — `mo` must be checked before `m`-anything.
    if spec.endswith("mo"):
        prefix = spec[:-2]
        if not prefix:
            raise ValueError(
                f"missing numeric prefix for month duration {spec!r} "
                f"— write `<N>mo` (e.g. `6mo`)"
            )
        try:
            n = int(prefix)
        except ValueError:
            raise ValueError(f"invalid duration {spec!r} — expected `<N>mo`")
        days = n * 30
    elif spec[-1] == "m":
        raise ValueError(
            f"ambiguous duration {spec!r} — use `Nmo` for months (e.g. `6mo`) "
            f"or `Nd` for days; bare `m` is reserved for future clarity"
        )
    elif spec[-1] in ("d", "w", "y"):
        n = int(spec[:-1])
        unit = spec[-1]
        days = {"d": n, "w": n * 7, "y": n * 365}[unit]
    else:
        days = int(spec)

    if days <= 0:
        raise ValueError(f"duration must be positive (got {spec})")
    # M2: cap at ~1000 years to prevent OverflowError in timedelta
    if days > 365_000:
        raise ValueError(f"Duration too large: {days} days (max ~1000 years)")
    return days


def _main_audit(argv: List[str]) -> int:
    """Handle `audit <file> [--dead-rules SPEC] [--bump ID]`."""
    if not argv:
        print(
            "Usage: trugs-memory audit <file> [--dead-rules SPEC] [--bump MEMORY_ID]",
            file=sys.stderr,
        )
        return 2

    path = Path(argv[0])
    dead_spec: Optional[str] = None
    bump_id: Optional[str] = None

    i = 1
    while i < len(argv):
        flag = argv[i]
        if flag == "--dead-rules" and i + 1 < len(argv):
            dead_spec = argv[i + 1]
            i += 2
        elif flag == "--bump" and i + 1 < len(argv):
            bump_id = argv[i + 1]
            i += 2
        else:
            print(f"Error: unknown argument '{flag}'", file=sys.stderr)
            return 2

    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    graph = load_graph(path)

    # Handle --bump (mutating) first.
    if bump_id is not None:
        if bump_hit(graph, bump_id):
            save_graph(path, graph)
            node = _find_node(graph, bump_id)
            hits = node["properties"].get("hit_count", 0)
            print(f"Bumped: {bump_id} (hit_count={hits})")
            return 0
        print(f"Error: memory '{bump_id}' not found", file=sys.stderr)
        return 1

    # Dead-rules report.
    threshold_days = 30
    if dead_spec is not None:
        try:
            threshold_days = _parse_duration_days(dead_spec)
        except ValueError:
            print(f"Error: invalid duration '{dead_spec}'", file=sys.stderr)
            return 2

    dead = dead_rules(graph, older_than_days=threshold_days)

    # Summary counters.
    total = sum(
        1 for n in graph.get("nodes", [])
        if n.get("id") != "memory-root" and n.get("parent_id") == "memory-root"
    )
    print(f"Memory store: {total} memories total.")
    print(f"Dead-rules threshold: {threshold_days} days.")
    if not dead:
        print("No dead feedback rules found.")
    else:
        print(f"{len(dead)} dead feedback rule(s):")
        for d in dead:
            body = d.rule or d.text
            short = body[:72] + ("…" if len(body) > 72 else "")
            print(f"  [{d.memory_id}] created={d.created}")
            print(f"    {short}")
    return 0


def _main_reconcile(argv: List[str]) -> int:
    """Handle `reconcile <file> [--threshold N] [--type TYPE]`."""
    if not argv:
        print(
            "Usage: trugs-memory reconcile <file> [--threshold N] [--type TYPE]",
            file=sys.stderr,
        )
        return 2

    path = Path(argv[0])
    threshold = DEFAULT_SIMILARITY_THRESHOLD
    memory_type: Optional[str] = None

    i = 1
    while i < len(argv):
        flag = argv[i]
        if flag == "--threshold" and i + 1 < len(argv):
            try:
                threshold = float(argv[i + 1])
            except ValueError:
                print(f"Error: --threshold requires a float, got '{argv[i + 1]}'", file=sys.stderr)
                return 2
            i += 2
        elif flag == "--type" and i + 1 < len(argv):
            memory_type = argv[i + 1]
            i += 2
        else:
            print(f"Error: unknown argument '{flag}'", file=sys.stderr)
            return 2

    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    graph = load_graph(path)
    candidates = reconcile_candidates(graph, threshold=threshold, memory_type=memory_type)

    if not candidates:
        print(f"No duplicate candidates at threshold {threshold:.2f}.")
        return 0

    print(f"{len(candidates)} candidate pair(s) at threshold {threshold:.2f}:")
    for c in candidates:
        print(f"  sim={c.similarity:.2f}  {c.a_id}  ↔  {c.b_id}")
        print(f"    A: {c.a_text[:100]}")
        print(f"    B: {c.b_text[:100]}")
    return 0


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main() -> None:
    """CLI entry: dispatches to `audit` or `reconcile` based on argv[1]."""
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    command = argv[0]
    rest = argv[1:]
    if command == "audit":
        sys.exit(_main_audit(rest))
    elif command == "reconcile":
        sys.exit(_main_reconcile(rest))
    else:
        print(f"Unknown command: {command}. Use 'audit' or 'reconcile'.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
