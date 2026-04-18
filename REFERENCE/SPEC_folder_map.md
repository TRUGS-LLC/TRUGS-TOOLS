# SPEC_folder_map.md — `trugs folder-map` Specification

**Version:** 1.0.0  
**Status:** ACTIVE  
**Last Updated:** 2026-02-22

---

## Purpose

`trugs folder-map` builds a root-level graph from all `folder.trug.json` files in the repository. It loads each TRUG's FOLDER node, resolves cross-folder edges (`folder_name:node_id`), and writes a unified root graph. This is the last command in the nightly pipeline — after `folder-sync`, `folder-check`, and `folder-render`.

**Design Philosophy:** Aggregate what individual TRUGs prove; resolve cross-folder references mechanically; report what cannot be resolved.

---

## Architecture

### Design Principles

1. **Read-only on individual TRUGs** — `folder-map` never modifies any subfolder's `folder.trug.json`. It only reads them and writes the root graph.
2. **Cross-folder resolution is the core job** — edges with `folder_name:node_id` in `to_id` (or `from_id`) are resolved by verifying the target folder and node exist.
3. **Filesystem is ground truth** — the set of folders and their contents comes from `find_all_folder_trugs()`. No hardcoded folder lists.
4. **Zero runtime dependencies** — only Python stdlib (`json`, `pathlib`, `os`, `re`, `typing`).
5. **Deterministic output** — same set of TRUGs produces byte-identical root graph. Nodes sorted by ID, edges sorted by (relation, from_id, to_id).
6. **Idempotent** — running `folder-map` twice produces the same output.

### Module Structure

```
trugs_tools/filesystem/folder_map.py
├── map_folder_trugs(root, dry_run, output) → MapResult  # Main entry point
├── _load_folder_trugs(trug_paths) → Dict[str, FolderInfo]  # Load + index
├── _folder_alias(folder_name) → str                      # TRUGS_TOOLS → trugs_tools
├── _resolve_cross_folder_edges(folders) → ResolveResult   # Resolution engine
├── _build_root_graph(folders, resolved) → dict            # Assemble root TRUG
├── _make_folder_node(alias, folder_info) → dict           # Create root node
└── _find_orphaned_folders(folders, edges) → List[str]     # Detect disconnected
```

Imports from folder_check.py:
  `find_all_folder_trugs`

### Map Pipeline

1. **Find** — discover all `folder.trug.json` files under root (excluding `zzz_*`).
2. **Load** — load each TRUG, extract FOLDER node and build folder index.
3. **Alias** — map each folder directory name to its lowercase alias (e.g., `TRUGS_TOOLS` → `trugs_tools`).
4. **Resolve** — scan all edges in all TRUGs for cross-folder references (`alias:node_id`). Verify targets exist.
5. **Build** — assemble root graph: one COMPONENT node per folder, `contains` edges from root, resolved cross-folder edges.
6. **Detect orphans** — identify folders with no cross-folder connections.
7. **Write** — write root `folder.trug.json` (or print if `--dry-run`).

---

## Map Rules

### MR-01: Folder Discovery

- Use `find_all_folder_trugs(root)` from `folder_check.py` to find all `folder.trug.json` files.
- Exclude the root `folder.trug.json` itself (it is the output, not an input).
- Each discovered TRUG represents one subfolder in the root graph.

### MR-02: Folder Alias Mapping

- The alias for a folder is its directory name lowercased: `TRUGS_TOOLS` → `trugs_tools`, `PORT_FACTORY` → `code_factory`.
- Cross-folder edge references use this alias as the prefix: `trugs_tools:comp_validator`.

### MR-03: Cross-Folder Edge Detection

- An edge is cross-folder if its `to_id` or `from_id` contains a `:` character.
- Parse format: `alias:node_id` where `alias` maps to a folder and `node_id` is a node within that folder's TRUG.

### MR-04: Edge Resolution

For each cross-folder edge:
1. Parse the `alias:node_id` reference.
2. Look up the alias in the folder index.
3. If alias not found → **unresolved** (target folder missing).
4. If alias found but node_id not in that TRUG's nodes → **unresolved** (target node missing).
5. If both exist → **resolved**.

### MR-05: Root Graph Assembly

- **Root node:** `id: "root_folder"`, `type: "FOLDER"`, with `contains` listing all folder node IDs.
- **Folder nodes:** One COMPONENT node per subfolder with `id: "folder_{alias}"`. Properties pulled from the subfolder's FOLDER node (`name`, `purpose`, `phase`, `status`, `version`).
- **Contains edges:** `root_folder` → each `folder_{alias}` with `relation: "contains"`.
- **Cross-folder edges:** For each resolved cross-folder edge, create a root-level edge from the source folder node to the target folder node, preserving the relation type. Deduplicate by (from_id, to_id, relation).

### MR-06: Orphan Detection

A folder is orphaned if it has zero cross-folder edges (neither source nor target of any cross-folder edge). These folders are still included in the root graph but flagged in the report.

### MR-07: Output Format

The root graph follows the same `folder.trug.json` schema:
```json
{
  "name": "TRUGS-DEVELOPMENT Root",
  "version": "1.0.0",
  "type": "PROJECT",
  "description": "Root-level TRUG ...",
  "dimensions": {
    "folder_structure": {
      "description": "Top-level monorepo structure",
      "base_level": "BASE"
    }
  },
  "capabilities": {
    "extensions": [],
    "vocabularies": ["project_v1"],
    "profiles": []
  },
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

### MR-08: Deterministic Output

- Nodes sorted by `id` alphabetically.
- Edges sorted by `(relation, from_id, to_id)`.
- JSON written with `indent=2` and trailing newline.

---

## CLI Interface

### Usage

```
trugs folder-map [ROOT]             Build root graph from all folder TRUGs
trugs folder-map --dry-run          Print root graph to stdout without writing
trugs folder-map --output FILE      Write to custom output path
trugs folder-map --root DIR         Scan from specific root directory
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `ROOT` | Current directory | Root directory to scan for folder.trug.json files |
| `--dry-run` | false | Print JSON to stdout instead of writing file |
| `--output FILE` | `ROOT/folder.trug.json` | Custom output file path |
| `--root DIR` | Current directory | Alias for ROOT positional arg |

### Output Format

```
Mapped 22 folder TRUGs → root graph
  Resolved: 6 cross-folder edges
  Unresolved: 0 edges
  Orphaned: 5 folders (PORT_FACTORY, HUB_LIBRARY, ...)
  Wrote: folder.trug.json (30 nodes, 28 edges)
```

### Exit Codes

- 0: Success (including when there are unresolved edges — they are warnings, not errors)
- 1: No folder.trug.json files found or invalid root path
- 2: Write error

---

## Test Strategy

### Unit Tests

| Test | Input | Expected |
|------|-------|----------|
| `test_folder_alias` | Various folder names | Correct lowercase aliases |
| `test_resolve_valid_edge` | Edge with valid cross-folder ref | Resolved |
| `test_resolve_missing_folder` | Edge targeting non-existent folder | Unresolved |
| `test_resolve_missing_node` | Edge targeting non-existent node | Unresolved |
| `test_build_root_graph_structure` | 3 folder TRUGs | Root with 3 COMPONENT nodes + edges |
| `test_deterministic_output` | Same input twice | Identical output |
| `test_orphan_detection` | Folder with no cross-folder edges | Listed as orphan |
| `test_dedup_cross_folder_edges` | Multiple edges A→B same relation | One edge in root |
| `test_excludes_root_trug` | Root has folder.trug.json | Not included as subfolder |

### Integration Tests

| Test | Input | Expected |
|------|-------|----------|
| `test_map_real_repo` | Run against TRUGS-DEVELOPMENT root | Valid root graph |
| `test_map_idempotent` | Map twice | Identical output |
| `test_map_then_validate` | Map → validate output | Passes `trugs-validate` |

### CLI Tests

| Test | Input | Expected |
|------|-------|----------|
| `test_cli_dry_run` | `--dry-run` | Stdout only, no file written |
| `test_cli_default` | No args | Writes root folder.trug.json |
| `test_cli_output` | `--output custom.json` | Writes to custom path |
| `test_cli_no_trugs` | Empty directory | Exit 1 |

### Coverage Target

≥90% coverage on `folder_map.py`.
