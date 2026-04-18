# SPEC_folder_sync.md — `trugs folder-sync` Specification

**Version:** 1.0.0  
**Status:** ACTIVE  
**Last Updated:** 2026-02-22

---

> **Implementation note (2026-03-20):** This command now uses `trugs-store`
> (`InMemoryGraphStore` + `JsonFilePersistence`) internally for all graph I/O.
> The bidirectional invariant (parent.contains ↔ child.parent_id ↔ CONTAINS edge)
> is enforced automatically by the store. See `TRUGS_STORE/SPEC_844_graphstore_protocol.py`.


## Purpose

`trugs folder-sync` updates an existing `folder.trug.json` with current filesystem facts without touching human-curated edges. It re-scans the folder, patches factual properties (counts, LOC, phase), detects new files, and flags stale nodes — preserving all human curation.

**Design Philosophy:** Patch what the filesystem proves; never discard what humans curated.

---

## Architecture

### Design Principles

1. **Diffing, not regenerating** — reads the existing TRUG and patches it in place. Never calls `init_folder_trug()` to replace the file.
2. **Edge preservation is the #1 invariant** — edges are never modified, added, or removed (except `contains` and `tests` edges for newly detected nodes).
3. **Filesystem is ground truth** — all counts come from `os.walk`, `Path.glob`, or subprocess calls. Never from prose documents.
4. **Zero runtime dependencies** — only Python stdlib (`json`, `pathlib`, `datetime`, `re`, `os`, `subprocess`, `typing`).
5. **Reuse folder-init scanners** — import scanning functions from `folder_init.py`. No duplicated scanner logic.
6. **Idempotent** — running `folder-sync` twice in a row produces the same output.

### Module Structure

```
trugs_tools/filesystem/folder_sync.py
├── sync_folder_trug(path, run_tests, dry_run) → SyncResult  # Main entry point
├── _match_nodes(existing, fresh) → MatchResult               # Node matching
├── _update_factual_properties(existing_node, fresh_node)      # Property patcher
├── _detect_stale_nodes(existing, fresh) → List[dict]          # Staleness detector
├── _detect_new_nodes(existing, fresh) → List[dict]            # New node detector
└── _update_folder_node(folder_node, metadata) → None          # FOLDER patcher

Imports from folder_init.py:
  _scan_documents, _scan_components, _scan_tests,
  _scan_schemas, _scan_templates, _scan_examples,
  _read_aaa_metadata, _read_pyproject_metadata
```

### Sync Pipeline

1. **Load** — read existing `folder.trug.json` into memory.
2. **Scan** — run all `folder_init` scanners to get fresh filesystem state.
3. **Match** — pair existing nodes to fresh nodes by `id`.
4. **Patch** — update factual properties on matched nodes; preserve human-curated properties.
5. **Flag stale** — mark unmatched existing nodes with `stale: true`.
6. **Add new** — append unmatched fresh nodes; add `contains`/`tests` edges for them.
7. **Update FOLDER** — patch FOLDER node metadata (phase, status, version, contains array).
8. **Update top-level** — patch top-level TRUG metadata from pyproject.toml.
9. **Write** — write back with `indent=2` and trailing newline (or print diff if `--dry-run`).

---

## Sync Rules

### SR-01: Property Update Rules

**Properties that folder-sync UPDATES** (factual, scannable):

| Property | Source | Node Types |
|----------|--------|------------|
| `file_count` | Count `.py` files | COMPONENT |
| `loc` | Count lines | COMPONENT |
| `test_count` | pytest or file count | TEST_SUITE |
| `test_files` | Count test files | TEST_SUITE |
| `schema_count` | Count schema files | SCHEMA |
| `template_count` | Count template files | TEMPLATE |
| `example_count` | Count example files | EXAMPLE_SET |
| `phase` | AAA.md | FOLDER |
| `status` | AAA.md | FOLDER |
| `version` | AAA.md or pyproject.toml | FOLDER + top-level |

**Properties that folder-sync PRESERVES** (human-curated):

| Property | Reason |
|----------|--------|
| `purpose` | Human may have enriched beyond generic inference |
| `verified`, `verified_by`, `verified_date` | Human verification flags |
| Any custom/unknown properties | Domain-specific info added by humans |

When updating a node, the scanner result is merged into the existing properties dict. Factual keys are overwritten; all other keys are left untouched.

### SR-02: Node Matching

Existing nodes are matched to fresh scan results by `id`. The `id` is the canonical key.

- **Match found:** Update factual properties per SR-01. If the node was previously stale, remove `stale` and `stale_reason`.
- **No match (existing only):** Node is stale → SR-04.
- **No match (fresh only):** Node is new → SR-03.

If a human renamed a node's `id`, it will appear as one stale node plus one new node. This is by design — IDs are stable identifiers.

### SR-03: New Node Detection

When a fresh scan produces a node whose `id` does not exist in the current TRUG:

1. Add the node to the `nodes` array.
2. Add the node's `id` to the FOLDER node's `contains` array.
3. Add a `contains` edge from the FOLDER node to the new node.
4. If the new node is a `TEST_SUITE`, add `tests` edges to all existing COMPONENT nodes.
5. If a new COMPONENT is added and a `TEST_SUITE` exists, add a `tests` edge from TEST_SUITE to the new COMPONENT.

These are the **only** cases where edges are added.

### SR-04: Staleness Detection

When an existing node has no matching fresh node (file/directory no longer on disk):

```json
{
  "stale": true,
  "stale_reason": "file not found on disk"
}
```

These properties are added to the node's `properties` dict. The node is **never removed**.

When a previously stale node's file reappears (match found on next sync), remove `stale` and `stale_reason` from properties and update factual properties as normal.

The FOLDER node is never marked stale.

### SR-05: Edge Preservation

**Hard invariant:** `folder-sync` never modifies, reorders, or removes existing edges.

The only edge mutations allowed are **additions** for newly detected nodes (SR-03). The total edge count before sync minus any new edges must equal the count of original edges after sync.

The `--dry-run` output reports: `Edges unchanged (N edges preserved)`.

### SR-06: FOLDER Node Update

The single FOLDER node (`parent_id: null`) receives these updates:

- `contains` array: append IDs of any new nodes (do not remove IDs of stale nodes).
- `phase`, `status`, `version`: update from `_read_aaa_metadata` / `_read_pyproject_metadata` (factual properties only).
- `purpose`: preserved if it differs from the generic inferred value.

### SR-07: Top-Level Metadata Update

The top-level TRUG dict (outside the `nodes`/`edges` arrays) is updated:

- `version`: from `pyproject.toml` if available (package version, not schema version).
- `description`: from `pyproject.toml` if available.
- All other top-level keys are preserved as-is.

---

## CLI Interface

### Usage

```
trugs folder-sync PATH              Sync one folder's TRUG with filesystem
trugs folder-sync --all             Sync all folders with existing folder.trug.json
trugs folder-sync PATH --dry-run    Print diff to stdout instead of writing
trugs folder-sync PATH --no-tests   Skip pytest subprocess for test counting
trugs folder-sync --all --root DIR  Scan from specific root directory
```

### Options

| Option | Description |
|--------|-------------|
| `PATH` | Target folder path (must contain `folder.trug.json`) |
| `--all` | Sync all folders that already have `folder.trug.json` |
| `--dry-run` | Print change summary to stdout, do not write file |
| `--no-tests` | Skip pytest subprocess for test counting |
| `--root DIR` | Root directory for `--all` scanning (default: cwd) |

### Output Format

**Default (non-dry-run):**

```
Synced TRUGS_TOOLS/folder.trug.json
  Updated: comp_trugs_tools (file_count: 45→47, loc: 3200→3350)
  Updated: test_suite (test_count: 1100→1141)
  New node: spec_folder_init (SPEC_folder_init.md)
  Stale: doc_removed (file not found)
  Edges unchanged (37 edges preserved)
```

**Dry-run:** Same format, prefixed with `[dry-run]`, no file written.

**No changes:** `No changes needed for PATH/folder.trug.json`

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (including "no changes needed") |
| 1 | No `folder.trug.json` found or invalid path |
| 2 | Write error |

---

## Test Strategy

### Test Fixtures

Tests use `tempfile.mkdtemp()` to create isolated folder structures with a pre-built `folder.trug.json`. Each test modifies the filesystem (add/remove files) and then syncs, asserting on the `SyncResult`.

### Comparison Rules

Sync results are validated for:

1. **Edge preservation** — edge count and content unchanged (except new-node edges)
2. **Factual property updates** — counts match filesystem reality
3. **Human property preservation** — custom `purpose`, `verified`, and unknown keys survive sync
4. **Stale detection** — removed files produce `stale: true` nodes
5. **New node detection** — added files produce new nodes with correct edges
6. **Idempotency** — second sync produces identical output to first
7. **Round-trip validity** — synced TRUG passes `folder-check` with zero new errors
