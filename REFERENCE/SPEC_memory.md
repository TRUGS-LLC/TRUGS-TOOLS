# SPEC: `tg memory` — TRUG-backed persistent memory

**Version:** 1.0.0
**Sub-namespace:** `tg memory <sub>`
**Python module:** `trugs_tools.memory`

## Purpose

A persistent memory store backed by a TRUG graph. Each memory is a node; associations between memories are edges. The graph validates against CORE, so memory storage inherits the same structural guarantees as any TRUG.

Primary consumer: Claude Code skills (`session-open`, `session-close`, `session-update`, `remember`) that capture durable cross-session state — architectural decisions, user preferences, conventions, external references.

## Storage

Memories live in a standard `.trug.json` file. Default path (for Claude Code):

```
~/.claude/projects/<slug>/memory/memory.trug.json
```

Any `.trug.json` file works — the storage path is always an explicit positional argument.

## Memory types

The store uses exactly four canonical types:

| Type | Purpose |
|---|---|
| `user` | Facts about the user (role, preferences, knowledge). |
| `feedback` | Guidance about how to approach work (corrections + validated approaches). |
| `project` | State of ongoing work (initiatives, decisions, incidents, external dates). |
| `reference` | Pointers to external systems (Linear, Slack, Grafana, etc.). |

No other values. Custom types are rejected.

## Commands

### `tg memory` (default)

```
tg memory
```

Show recent memories from the default store. Equivalent to `tg memory recall` with no query.

### `tg memory remember`

```
tg memory remember FILE TEXT [flags]
```

Write a memory. Flags:

| Flag | Purpose |
|---|---|
| `--type TYPE` | One of `user`, `feedback`, `project`, `reference`. Default: `FACT` (legacy; always pass explicitly). |
| `--rule RULE` | Terse, executable form of the memory. Renderers prefer this over `text`. Keep load-bearing. |
| `--rationale TEXT` | Explanatory prose. Not rendered to `MEMORY.md` by default; available on `--include-rationale` renders. |
| `--tag TAG` | Attach a tag. May be repeated. |
| `--tags A,B,C` | Legacy comma-separated form. |
| `--source URL` | Optional citation. |
| `--session-id ID` | Identifier for the session that wrote this memory. |
| `--supersede OLD_ID` | Replace an older memory — closes it (`valid_to=now`, `superseded_by=<new>`) and creates a `SUPERSEDES` edge. If the old memory is already superseded, the new one links to the tail of the chain. |
| `--valid-to ISO8601` | Explicit expiration timestamp. |

On success: `Remembered: mem-<id>` to stdout. Exit 0.

### `tg memory recall`

```
tg memory recall FILE QUERY
```

Substring search (case-insensitive) across a memory's `text`, `rule`, `tags`, and `type`. Prints matching `mem-<id>` rows with a short preview.

### `tg memory forget`

```
tg memory forget FILE ID
```

Close a memory (`valid_to=now`). Does not delete — the memory remains in the graph for provenance. Use `--supersede` on a new `remember` to record what replaced it.

### `tg memory associate`

```
tg memory associate FILE FROM_ID TO_ID [--relation REL]
```

Create an edge between two memories. Relations must be TRL prepositions (`FEEDS`, `SUPERSEDES`, `REFERENCES`, `GROUNDS`, etc.). Default relation: `REFERENCES`.

### `tg memory render`

```
tg memory render INPUT.trug.json OUTPUT.md [--budget BYTES]
```

Render the memory graph to a `MEMORY.md` summary suitable for Claude Code's auto-loaded memory surface.

Render rules:

- Group by `type` in canonical order: `user`, `feedback`, `project`, `reference`.
- Within each group, prefer `rule` over `text` for the headline.
- Skip memories whose `valid_to` is in the past.
- `--budget BYTES` truncates the output to approximately that many bytes, deterministically.

Must be idempotent — re-rendering the same input yields byte-identical output. Pure function of the graph; no wall-clock timestamps in the header.

### `tg memory audit`

```
tg memory audit FILE
```

Integrity check:

- **Dead rules** — memories never recalled (zero hits over N days).
- **Orphans** — memories with no associations.
- **Chain integrity** — `SUPERSEDES` edges form acyclic chains; no forks.
- **Schema** — every memory has `type`, `text`, `created`; required fields per type.

Exit 1 if any critical issue; warnings printed to stderr.

### `tg memory import`

```
tg memory import FILE --from PATH
```

Bulk-import legacy memory formats (flat `.md` files with frontmatter, earlier session-memory directories). Assigns new `mem-<id>`s, preserves `created` timestamps where present.

### `tg memory reconcile`

```
tg memory reconcile FILE [--threshold N]
```

Surface near-duplicate memory pairs for human merge review. Threshold is similarity (0.0–1.0); default `0.7`.

Output format:

```
Reconcile candidates (sim ≥ 0.70):
  sim=0.85  mem-aaaa  ↔  mem-bbbb
    A: <text>
    B: <text>
```

Never auto-merges. User reviews and issues `tg memory remember --supersede <old_id>` (via the `/remember` skill) to act on a pair.

## Schema

Each memory is a TRUG node:

```json
{
  "id": "mem-<8-hex>",
  "type": "DATA",
  "properties": {
    "type": "project",
    "text": "Full prose description + why + how to apply.",
    "rule": "Terse one-line executable form.",
    "rationale": "Why paragraph, prose.",
    "tags": ["1576", "reorg", "session-2026-04-18"],
    "source": "https://github.com/...",
    "session_id": "2026-04-18",
    "created": "2026-04-18T14:23:01+00:00",
    "valid_to": null,
    "superseded_by": null
  },
  "parent_id": null,
  "contains": [],
  "metric_level": "BASE_MEMORY",
  "dimension": "persistent_memory"
}
```

## Integration with Claude Code skills

The `session-open`, `session-close`, `session-update`, and `remember` skills in the user's `.claude/skills/` directory invoke `tg memory` via subprocess. The canonical wrapper:

```bash
tg memory remember "$MEM_PATH" "$DECISION_TEXT" \
    --type project \
    --rule "Terse executable form" \
    --rationale "$RATIONALE" \
    --tag "session-$(date +%Y-%m-%d)" \
    --session-id "$(date +%Y-%m-%d)"
```

## See also

- [`SPEC_cli.md`](./SPEC_cli.md) — full `tg` CLI surface
- [`SPEC_validator.md`](./SPEC_validator.md) — the CORE validator that memories pass
- Claude Code skill definitions — `/session-open`, `/session-close`, `/session-update`, `/remember`
