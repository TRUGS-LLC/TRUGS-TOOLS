# TRUGS Filesystem Commands

TRUGS filesystem commands provide graph-enriched folder operations. Every command works with `folder.trug.json` — a single source of truth that tracks your project's files, their types, relationships, and dimensions.

## Quick Start

```bash
# Initialize a project graph
trugs tinit . --scan

# List files with graph metadata
trugs tls .

# Find all source files
trugs tfind -t SOURCE

# Create a dependency edge
trugs tlink main_py utils_py -r DEPENDS_ON

# Regenerate docs from graph
trugs twatch . --once

# Sync graph with filesystem
trugs tsync .
```

## Commands Reference

### `tinit` — Initialize folder.trug.json

Creates a `folder.trug.json` in the target directory with a FOLDER root node.

```bash
trugs tinit [DIRECTORY] [-n NAME] [-d DESCRIPTION] [--scan] [--force]
```

| Flag | Description |
|------|-------------|
| `DIRECTORY` | Target directory (default: `.`) |
| `-n, --name` | Project name (default: directory name) |
| `-d, --description` | Project description |
| `--scan` | Scan directory for existing files and add them |
| `--force` | Overwrite existing folder.trug.json |

**Examples:**
```bash
trugs tinit .                          # Basic init
trugs tinit . --scan                   # Init and discover files
trugs tinit . -n MyProject -d "desc"   # Init with metadata
trugs tinit . --force --scan           # Re-initialize with scan
```

---

### `tadd` — Add files to graph

Adds file nodes to `folder.trug.json`, inferring node type from file extension.

```bash
trugs tadd FILE [FILE...] [-C DIR] [-t TYPE] [-p PARENT] [--purpose TEXT]
```

| Flag | Description |
|------|-------------|
| `FILE` | File(s) to add |
| `-C, --directory` | Directory containing folder.trug.json |
| `-t, --type` | Override inferred node type |
| `-p, --parent` | Parent node ID (default: root) |
| `--purpose` | Purpose description |

**Type inference:**
| Extension | Node Type |
|-----------|-----------|
| `.py`, `.go`, `.rs`, `.js`, `.ts` | SOURCE |
| `.md`, `.txt`, `.rst` | DOCUMENT |
| `.json`, `.yaml`, `.toml` | CONFIGURATION |
| `.trug.json` | SPECIFICATION |
| `.test.py`, `_test.go` | TEST |

**Examples:**
```bash
trugs tadd main.py utils.py -C .
trugs tadd data.csv -t CONFIGURATION
trugs tadd module.py -p lib_folder --purpose "Core library"
```

---

### `tls` — List with graph enrichment

Lists directory contents with TRUG metadata: node type, edge count, dimensions.

```bash
trugs tls [DIRECTORY] [--node ID] [--edges] [-f FORMAT]
```

| Flag | Description |
|------|-------------|
| `DIRECTORY` | Directory to list (default: `.`) |
| `--node` | List children of specific node |
| `--edges` | Show edge details |
| `-f, --format` | Output format: `text` (default) or `json` |

**Example output:**
```
Contents of: MyProject
========================
  [SOURCE        ] main.py  (1 edge)  dim=folder_structure
    └─ main_py --[DEPENDS_ON]--> utils_py
  [SOURCE        ] utils.py  dim=folder_structure
  [DOCUMENT      ] README.md  dim=folder_structure
```

---

### `tcd` — Graph-based navigation

Navigate the TRUG graph by node ID, parent, or root.

```bash
trugs tcd [TARGET] [-C DIR] [--current ID] [-f FORMAT]
```

| Flag | Description |
|------|-------------|
| `TARGET` | Node ID, `..` for parent, `/` for root |
| `-C, --directory` | Directory containing folder.trug.json |
| `--current` | Current node ID (needed for `..`) |
| `-f, --format` | Output format: `text` or `json` |

**Examples:**
```bash
trugs tcd /                          # Go to root
trugs tcd main_py                    # Go to specific node
trugs tcd .. --current main_py       # Go to parent
```

---

### `tfind` — Graph query engine

Query nodes by type, name pattern, dimension, edge relation, and more.

```bash
trugs tfind [-C DIR] [-t TYPE] [-n PATTERN] [-d DIM] [-e REL] [-m LEVEL] [-f FORMAT]
```

| Flag | Description |
|------|-------------|
| `-t, --type` | Filter by node type (SOURCE, DOCUMENT, etc.) |
| `-n, --name` | Filter by name (regex pattern) |
| `-d, --dimension` | Filter by dimension name |
| `-e, --edge-relation` | Filter by edge relation |
| `-m, --metric-level` | Filter by metric level |
| `-f, --format` | Output format: `text` or `json` |

**Examples:**
```bash
trugs tfind -t SOURCE                    # All source files
trugs tfind -n "\.py$"                   # All Python files
trugs tfind -t DOCUMENT -d folder_structure  # Docs in folder dim
trugs tfind -e DEPENDS_ON -f json        # Nodes with dependencies
```

---

### `tmove` — Atomic file move + graph update

Renames a file and updates all graph references atomically. On failure, both filesystem and graph are rolled back.

```bash
trugs tmove NODE_ID [-C DIR] [--name NEW_NAME] [--parent NEW_PARENT_ID]
```

| Flag | Description |
|------|-------------|
| `NODE_ID` | Node ID to move/rename |
| `--name` | New filename |
| `--parent` | New parent node ID |

**Examples:**
```bash
trugs tmove main_py --name app.py           # Rename
trugs tmove utils_py --parent lib_folder    # Reparent
trugs tmove old_py --name new.py --parent sub  # Both
```

**Atomicity:** If any step fails, the operation is fully rolled back — both the physical file and the graph state are restored.

---

### `tlink` — Create typed edges

Create or remove typed edges between nodes. Validates edge types and referential integrity.

```bash
trugs tlink FROM_ID TO_ID -r RELATION [-C DIR] [--remove]
```

| Flag | Description |
|------|-------------|
| `FROM_ID` | Source node ID |
| `TO_ID` | Target node ID |
| `-r, --relation` | Edge relation type |
| `--remove` | Remove the edge instead of creating |

**Valid relations:**
`CONFIGURES`, `CONTAINS`, `DEPENDS_ON`, `DOCUMENTS`, `EXTENDS`, `GENERATES`, `IMPLEMENTS`, `ORCHESTRATES`, `REFERENCES`, `RENDERS`, `TESTS`, `VALIDATES`

**Examples:**
```bash
trugs tlink main_py utils_py -r DEPENDS_ON
trugs tlink test_py main_py -r TESTS
trugs tlink main_py utils_py -r DEPENDS_ON --remove
```

---

### `tdim` — Dimension management

Add, remove, list, and assign dimensions to nodes.

```bash
trugs tdim ACTION [-C DIR] [-n NAME] [-d DESC] [--base-level LVL] [--node ID] [--force] [-f FORMAT]
```

| Action | Description |
|--------|-------------|
| `add` | Add a new dimension |
| `remove` | Remove a dimension |
| `list` | List all dimensions |
| `set` | Assign dimension to a node |

**Examples:**
```bash
trugs tdim list                                      # List dimensions
trugs tdim add -n security -d "Security audit"       # Add dimension
trugs tdim set --node main_py -n security            # Assign to node
trugs tdim remove -n security --force                # Remove (force)
```

---

### `twatch` — Monitor + auto-regenerate

Watches `folder.trug.json` for changes and regenerates AAA.md, README.md, and ARCHITECTURE.md.

```bash
trugs twatch [DIRECTORY] [--interval SECS] [--once]
```

| Flag | Description |
|------|-------------|
| `DIRECTORY` | Directory to watch (default: `.`) |
| `--interval` | Polling interval in seconds (default: 1.0) |
| `--once` | Run once and exit |

**Examples:**
```bash
trugs twatch .              # Watch continuously
trugs twatch . --once       # Render once and exit
trugs twatch . --interval 5 # Check every 5 seconds
```

---

### `tsync` — Discover files + infer edges

Synchronizes `folder.trug.json` with actual directory contents. Discovers new files, detects removed files, and optionally infers edges from file contents (imports, references).

```bash
trugs tsync [DIRECTORY] [--dry-run] [--no-edges]
```

| Flag | Description |
|------|-------------|
| `DIRECTORY` | Directory to sync (default: `.`) |
| `--dry-run` | Show changes without modifying graph |
| `--no-edges` | Don't infer edges from file contents |

**Edge inference supports:**
- Python: `import X`, `from X import Y`
- Markdown: `[text](file.md)` links

**Examples:**
```bash
trugs tsync .                  # Full sync
trugs tsync . --dry-run        # Preview changes
trugs tsync . --no-edges       # Sync files only
```

---

## Workflow Examples

### New Project Setup
```bash
mkdir my-project && cd my-project
trugs tinit . -n "My Project" -d "Description" --scan
trugs tls .                    # Review discovered files
trugs tlink src_py test_py -r TESTS
trugs twatch . --once          # Generate docs
```

### Ongoing Development
```bash
# After adding new files:
trugs tsync .                  # Discover and add them

# Check project structure:
trugs tls . --edges            # See relationships

# Find specific files:
trugs tfind -t SOURCE -n "test"  # Find test files
```

### Documentation Generation
```bash
trugs twatch .                 # Keep docs in sync (Ctrl+C to stop)
# OR
trugs twatch . --once          # One-shot render
```
