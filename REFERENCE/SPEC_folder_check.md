# TRUGS_TOOLS: Folder Check Specification

**Version:** 1.0.0 (AAA_AARDVARK)
**Component:** TRUGS_TOOLS Folder Check
**Status:** ✅ Specification Complete
**Last Updated:** 2026-02-21
**Parent:** [AAA.md](AAA.md)

---

> **Implementation note (2026-03-20):** This command now uses `trugs-store`
> (`InMemoryGraphStore` + `JsonFilePersistence`) internally for all graph I/O.
> The bidirectional invariant (parent.contains ↔ child.parent_id ↔ CONTAINS edge)
> is enforced automatically by the store. See `TRUGS_STORE/SPEC_844_graphstore_protocol.py`.


## Purpose

The `trugs folder-check` command validates `folder.trug.json` files against the
governance specification defined in
[TRUGS_FILES/SPEC_folder_governance.md](../TRUGS_FILES/SPEC_folder_governance.md).
It checks structural integrity, node/edge validity, cross-folder edge syntax,
filesystem existence, and contains-array consistency.

**What it validates:**

- ✅ Valid JSON structure and required top-level keys
- ✅ Exactly one root FOLDER node per file
- ✅ Node types against the 8-type governance vocabulary
- ✅ Metric level correctness for each node type
- ✅ Internal and cross-folder edge relation vocabularies
- ✅ Cross-folder edge `to_id` syntax (`folder_name:node_id`)
- ✅ Contains-array ↔ contains-edge consistency
- ✅ No dangling internal edge references
- ✅ Filesystem existence for DOCUMENT / SPECIFICATION nodes

**What it warns about:**

- ⚠️ On-disk items not represented by any node
- ⚠️ Nodes flagged `stale=true`
- ⚠️ FOLDER node with an empty `contains` array

**What it does NOT validate:**

- ❌ TRUGS CORE rules (node-field counts, hierarchy ordering, dimensions) — see Validator
- ❌ Property schemas (properties are open by convention)
- ❌ Phase / status drift against AAA.md (planned as W-04)

---

## Architecture

### Design Principles

1. **Single-Pass Pipeline** — All 11 error rules and 3 warning rules execute in
   one traversal of the parsed JSON, building lookup maps once and reusing them.
2. **Zero Dependencies Beyond Stdlib** — Only `json`, `os`, `pathlib`, `re`,
   and `typing` from Python's standard library. No third-party packages at
   runtime.
3. **CheckResult Dataclass** — Every check produces a `CheckResult` object with
   `errors`, `warnings`, `node_count`, and `edge_count`. The `.ok` property is
   `True` when `errors` is empty.
4. **Multi-File Scanning** — `find_all_folder_trugs()` walks the directory tree,
   pruning `zzz_*` and hidden directories, collecting every `folder.trug.json`.
5. **Fail-Fast on Structure** — If the file cannot be parsed as JSON or is
   missing required top-level keys, the checker returns immediately without
   attempting semantic checks.
6. **Deterministic Output** — Error and warning messages are appended in rule
   order (E-01 through E-11, then W-01 through W-03) for predictable output.

### Module Structure

```
trugs_tools/
└── filesystem/
    └── folder_check.py      # All validation logic, scanning, formatting
```

| Symbol                      | Kind       | Description                                       |
|-----------------------------|------------|---------------------------------------------------|
| `VALID_NODE_TYPES`          | `Dict`     | 8-entry mapping of node type → metric_level       |
| `VALID_INTERNAL_RELATIONS`  | `Set`      | 8 allowed relation strings for intra-folder edges |
| `VALID_CROSS_FOLDER_RELATIONS` | `Set`   | 5 allowed relation strings for cross-folder edges |
| `REQUIRED_TOP_LEVEL_KEYS`   | `Set`      | 7 keys every folder.trug.json must have           |
| `IGNORE_ON_DISK`            | `Set`      | Filenames excluded from W-01 on-disk checks       |
| `CheckResult`               | `class`    | Result container with errors, warnings, stats     |
| `check_folder_trug()`       | `function` | Validate a single file; returns `CheckResult`     |
| `find_all_folder_trugs()`   | `function` | Discover all `folder.trug.json` under a root      |
| `check_all()`               | `function` | Batch-check multiple files or directories         |
| `format_text()`             | `function` | Render results as human-readable text              |
| `format_json()`             | `function` | Render results as a JSON array                     |

### Validation Pipeline

```
Input: path to folder.trug.json
  ↓
E-01  Parse JSON (fail-fast on syntax error / missing file)
  ↓
E-02  Check required top-level keys (fail-fast if any missing)
  ↓
      Build lookup maps: node_ids, node_by_id, folder_nodes
  ↓
E-03  Exactly 1 FOLDER node with parent_id=null
  ↓
E-04  Validate all node types ∈ VALID_NODE_TYPES
  ↓
E-05  Validate metric_level matches type
  ↓
E-06  Validate internal edge relations ∈ VALID_INTERNAL_RELATIONS
E-07  Validate cross-folder edge relations ∈ VALID_CROSS_FOLDER_RELATIONS
E-08  Validate cross-folder to_id syntax (folder_name:node_id)
  ↓
E-09  Contains-array ↔ contains-edge consistency
  ↓
E-10  No dangling edge references (internal from_id / to_id)
  ↓
E-11  Filesystem existence for DOCUMENT / SPECIFICATION nodes
  ↓
W-01  On-disk items not in TRUG
W-02  Stale flags
W-03  Empty contains array
  ↓
Output: CheckResult
```

---

## Governance Constants

All constants are defined at module scope and derived from
`TRUGS_FILES/SPEC_folder_governance.md`.

### VALID_NODE_TYPES

Maps each allowed `type` string to its required `metric_level`.

| Node Type        | Required `metric_level` |
|------------------|-------------------------|
| `FOLDER`         | `KILO_FOLDER`           |
| `DOCUMENT`       | `BASE_DOCUMENT`         |
| `SPECIFICATION`  | `BASE_SPECIFICATION`    |
| `COMPONENT`      | `DEKA_COMPONENT`        |
| `TEST_SUITE`     | `BASE_TEST_SUITE`       |
| `EXAMPLE_SET`    | `BASE_EXAMPLE_SET`      |
| `SCHEMA`         | `BASE_SCHEMA`           |
| `TEMPLATE`       | `BASE_TEMPLATE`         |

**Implementation:**

```python
VALID_NODE_TYPES: Dict[str, str] = {
    "FOLDER":        "KILO_FOLDER",
    "DOCUMENT":      "BASE_DOCUMENT",
    "SPECIFICATION": "BASE_SPECIFICATION",
    "COMPONENT":     "DEKA_COMPONENT",
    "TEST_SUITE":    "BASE_TEST_SUITE",
    "EXAMPLE_SET":   "BASE_EXAMPLE_SET",
    "SCHEMA":        "BASE_SCHEMA",
    "TEMPLATE":      "BASE_TEMPLATE",
}
```

### VALID_INTERNAL_RELATIONS

The 8 relation strings permitted on edges where `to_id` does **not** contain a
colon (i.e., both endpoints are in the same folder TRUG).

| Relation      | Semantic                                         |
|---------------|--------------------------------------------------|
| `contains`    | Parent → child containment                       |
| `uses`        | Node depends on / imports another node           |
| `produces`    | Node generates / outputs another node            |
| `validates`   | Node validates correctness of another node       |
| `implements`  | Node implements a specification or interface     |
| `tests`       | Test suite targets another node                  |
| `describes`   | Documentation describes another node             |
| `governs`     | Specification governs structure of another node  |

**Implementation:**

```python
VALID_INTERNAL_RELATIONS: Set[str] = {
    "contains", "uses", "produces", "validates",
    "implements", "tests", "describes", "governs",
}
```

### VALID_CROSS_FOLDER_RELATIONS

The 5 relation strings permitted on edges where `to_id` contains a colon
(`folder_name:node_id`), indicating a reference to a node in a different
folder's TRUG.

| Relation             | Semantic                                            |
|----------------------|-----------------------------------------------------|
| `uses`               | This folder depends on a node in another folder     |
| `implements`         | This folder implements a spec in another folder     |
| `has_reference_impl` | This folder is the reference implementation         |
| `validates`          | This folder validates a node in another folder      |
| `produces`           | This folder produces output consumed by another     |

**Implementation:**

```python
VALID_CROSS_FOLDER_RELATIONS: Set[str] = {
    "uses", "implements", "has_reference_impl",
    "validates", "produces",
}
```

### REQUIRED_TOP_LEVEL_KEYS

Every `folder.trug.json` file must contain all 7 keys at the root level.

| Key              | Expected Type | Description                              |
|------------------|---------------|------------------------------------------|
| `name`           | `string`      | Human-readable folder name               |
| `version`        | `string`      | TRUGS spec version (e.g., `"1.0.0"`)    |
| `type`           | `string`      | Graph type (e.g., `"PROJECT"`)           |
| `dimensions`     | `object`      | Dimension declarations                   |
| `capabilities`   | `object`      | Extensions, vocabularies, profiles       |
| `nodes`          | `array`       | Node list                                |
| `edges`          | `array`       | Edge list                                |

**Implementation:**

```python
REQUIRED_TOP_LEVEL_KEYS: Set[str] = {
    "name", "version", "type", "dimensions",
    "capabilities", "nodes", "edges",
}
```

### IGNORE_ON_DISK

Files and directories excluded from the W-01 "on-disk items not in TRUG"
warning. These are build artifacts, caches, and the TRUG file itself.

```python
IGNORE_ON_DISK: Set[str] = {
    "folder.trug.json", "folder.trug.json.backup",
    ".git", "__pycache__", ".pytest_cache", "node_modules",
    ".mypy_cache", "htmlcov", ".coverage", ".tox",
    ".eggs", "dist", "build", ".DS_Store",
}
```

Additionally, any entry starting with `.` (hidden files) or `zzz_` (archived
items) is silently skipped, as are directories ending in `.egg-info`.

---

## Error-Level Rules

All error-level rules have **severity = ERROR**. Any error causes
`CheckResult.ok` to be `False` and the CLI to exit with code `1`.

### E-01: Valid JSON

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-01`                                                       |
| **Name**    | Valid JSON                                                   |
| **Severity**| ERROR                                                        |
| **Description** | The file must parse as valid JSON. If the file does not exist or contains syntax errors, no further checks are possible. |
| **Error Message Template** | `Invalid JSON: {json_decode_error_detail}` or `File not found: {path}` |

**Fail-fast:** Returns immediately on failure — no subsequent rules execute.

**Implementation detail:** Also rejects top-level values that are not JSON
objects (`"Top-level value must be a JSON object"`).

```python
try:
    with open(trug_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except json.JSONDecodeError as exc:
    result.errors.append(f"Invalid JSON: {exc}")
    return result
except FileNotFoundError:
    result.errors.append(f"File not found: {trug_path}")
    return result
```

---

### E-02: Required Top-Level Keys

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-02`                                                       |
| **Name**    | Required Top-Level Keys                                      |
| **Severity**| ERROR                                                        |
| **Description** | The root JSON object must contain all 7 required keys: `name`, `version`, `type`, `dimensions`, `capabilities`, `nodes`, `edges`. |
| **Error Message Template** | `Missing required top-level key: '{key}'` |

**Fail-fast:** Returns immediately if any key is missing — the checker cannot
build node/edge lookup maps without `nodes` and `edges`.

```python
missing_keys = REQUIRED_TOP_LEVEL_KEYS - set(data.keys())
for key in sorted(missing_keys):
    result.errors.append(f"Missing required top-level key: '{key}'")
if missing_keys:
    return result
```

---

### E-03: Single FOLDER Node

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-03`                                                       |
| **Name**    | Single FOLDER Node                                           |
| **Severity**| ERROR                                                        |
| **Description** | There must be exactly one node with `type="FOLDER"` and `parent_id=null`. This is the root node representing the folder itself. |
| **Error Message Template (zero)** | `No FOLDER node with parent_id=null found` |
| **Error Message Template (many)** | `Multiple FOLDER nodes with parent_id=null: {id1}, {id2}, ...` |

```python
root_folder_nodes = [n for n in folder_nodes if n.get("parent_id") is None]
if len(root_folder_nodes) == 0:
    result.errors.append("No FOLDER node with parent_id=null found")
elif len(root_folder_nodes) > 1:
    ids = [n.get("id", "?") for n in root_folder_nodes]
    result.errors.append(
        f"Multiple FOLDER nodes with parent_id=null: {', '.join(ids)}"
    )
```

---

### E-04: Valid Node Types

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-04`                                                       |
| **Name**    | Valid Node Types                                             |
| **Severity**| ERROR                                                        |
| **Description** | Every node's `type` field must be one of the 8 types defined in `VALID_NODE_TYPES`: FOLDER, DOCUMENT, SPECIFICATION, COMPONENT, TEST_SUITE, EXAMPLE_SET, SCHEMA, TEMPLATE. |
| **Error Message Template** | `Node '{node_id}': invalid type '{type}' (valid: COMPONENT, DOCUMENT, EXAMPLE_SET, FOLDER, SCHEMA, SPECIFICATION, TEMPLATE, TEST_SUITE)` |

```python
for node in nodes:
    ntype = node.get("type", "")
    nid = node.get("id", "?")
    if ntype not in VALID_NODE_TYPES:
        result.errors.append(
            f"Node '{nid}': invalid type '{ntype}' "
            f"(valid: {', '.join(sorted(VALID_NODE_TYPES))})"
        )
```

---

### E-05: Correct Metric Levels

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-05`                                                       |
| **Name**    | Correct Metric Levels                                        |
| **Severity**| ERROR                                                        |
| **Description** | Each node type maps to exactly one `metric_level`. For example, every `FOLDER` node must have `metric_level="KILO_FOLDER"`. A mismatch indicates a governance violation. |
| **Error Message Template** | `Node '{node_id}': metric_level '{actual}' should be '{expected}' for type '{type}'` |

```python
for node in nodes:
    ntype = node.get("type", "")
    nid = node.get("id", "?")
    mlevel = node.get("metric_level", "")
    expected = VALID_NODE_TYPES.get(ntype)
    if expected and mlevel != expected:
        result.errors.append(
            f"Node '{nid}': metric_level '{mlevel}' should be "
            f"'{expected}' for type '{ntype}'"
        )
```

---

### E-06: Valid Internal Edge Relations

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-06`                                                       |
| **Name**    | Valid Internal Edge Relations                                |
| **Severity**| ERROR                                                        |
| **Description** | Edges where `to_id` does **not** contain a colon are internal edges. Their `relation` must be one of the 8 values in `VALID_INTERNAL_RELATIONS`. |
| **Error Message Template** | `Edge '{from_id}' -> '{to_id}': invalid internal relation '{relation}' (valid: contains, describes, governs, implements, produces, tests, uses, validates)` |

```python
if not is_cross_folder:
    if relation not in VALID_INTERNAL_RELATIONS:
        result.errors.append(
            f"Edge '{from_id}' -> '{to_id}': invalid internal "
            f"relation '{relation}' "
            f"(valid: {', '.join(sorted(VALID_INTERNAL_RELATIONS))})"
        )
```

---

### E-07: Valid Cross-Folder Edge Relations

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-07`                                                       |
| **Name**    | Valid Cross-Folder Edge Relations                            |
| **Severity**| ERROR                                                        |
| **Description** | Edges where `to_id` contains a colon are cross-folder edges. Their `relation` must be one of the 5 values in `VALID_CROSS_FOLDER_RELATIONS`. |
| **Error Message Template** | `Edge '{from_id}' -> '{to_id}': invalid cross-folder relation '{relation}' (valid: has_reference_impl, implements, produces, uses, validates)` |

```python
if is_cross_folder:
    if relation not in VALID_CROSS_FOLDER_RELATIONS:
        result.errors.append(
            f"Edge '{from_id}' -> '{to_id}': invalid cross-folder "
            f"relation '{relation}' "
            f"(valid: {', '.join(sorted(VALID_CROSS_FOLDER_RELATIONS))})"
        )
```

---

### E-08: Cross-Folder Edge Syntax

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-08`                                                       |
| **Name**    | Cross-Folder Edge Syntax                                     |
| **Severity**| ERROR                                                        |
| **Description** | A `to_id` containing a colon must follow the format `folder_name:node_id`. Both parts must be non-empty. |
| **Error Message Template** | `Edge '{from_id}' -> '{to_id}': cross-folder to_id must have format 'folder_name:node_id'` |

**Examples:**

| `to_id`                      | Valid? | Reason                          |
|------------------------------|--------|---------------------------------|
| `TRUGS_TOOLS:comp_validator` | ✅     | Both parts non-empty            |
| `OTHER:some_node`            | ✅     | Both parts non-empty            |
| `:node_only`                 | ❌     | Empty folder name               |
| `folder_only:`               | ❌     | Empty node id                   |
| `a:b:c`                      | ❌     | More than one colon             |

```python
parts = str(to_id).split(":")
if len(parts) != 2 or not parts[0] or not parts[1]:
    result.errors.append(
        f"Edge '{from_id}' -> '{to_id}': cross-folder to_id must "
        f"have format 'folder_name:node_id'"
    )
```

---

### E-09: Contains-Array Consistency

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-09`                                                       |
| **Name**    | Contains-Array Consistency                                   |
| **Severity**| ERROR                                                        |
| **Description** | Every ID listed in the root FOLDER node's `contains` array must have a corresponding `contains` edge from the FOLDER node to that child. If a child appears in the array but has no matching edge, the TRUG is inconsistent. |
| **Error Message Template** | `Contains-array lists '{child_id}' but no 'contains' edge from '{folder_id}' to '{child_id}' exists` |

**Logic:**

1. Collect all `to_id` values from edges where `from_id == folder_id` and
   `relation == "contains"`.
2. For every ID in `folder_node["contains"]`, verify it appears in that set.

```python
if folder_node is not None:
    contains_list = folder_node.get("contains", [])
    contains_edges_to: Set[str] = set()
    folder_id = folder_node.get("id", "")
    for edge in edges:
        if (
            edge.get("from_id") == folder_id
            and edge.get("relation") == "contains"
        ):
            contains_edges_to.add(edge.get("to_id", ""))

    for child_id in contains_list:
        if child_id not in contains_edges_to:
            result.errors.append(
                f"Contains-array lists '{child_id}' but no 'contains' "
                f"edge from '{folder_id}' to '{child_id}' exists"
            )
```

---

### E-10: No Dangling Edge References

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-10`                                                       |
| **Name**    | No Dangling Edge References                                  |
| **Severity**| ERROR                                                        |
| **Description** | Every `from_id` must reference an existing node. Every `to_id` that is an internal reference (no colon) must also reference an existing node. Cross-folder `to_id` values (containing `:`) are exempt — the target node lives in another TRUG. |
| **Error Message Template (from)** | `Edge from_id '{from_id}' does not reference any node` |
| **Error Message Template (to)**   | `Edge to_id '{to_id}' does not reference any node`   |

```python
for edge in edges:
    from_id = edge.get("from_id", "")
    to_id = edge.get("to_id", "")
    if from_id not in node_ids:
        result.errors.append(
            f"Edge from_id '{from_id}' does not reference any node"
        )
    if ":" not in str(to_id) and to_id not in node_ids:
        result.errors.append(
            f"Edge to_id '{to_id}' does not reference any node"
        )
```

---

### E-11: Filesystem Existence

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `E-11`                                                       |
| **Name**    | Filesystem Existence                                         |
| **Severity**| ERROR                                                        |
| **Description** | Nodes of type `DOCUMENT` or `SPECIFICATION` that have a `properties.name` field must reference a file that actually exists on disk in the same directory as the `folder.trug.json`. This check is gated by the `check_filesystem` parameter. |
| **Error Message Template** | `Node '{node_id}' references file '{name}' but it does not exist in {folder_dir}` |

```python
folder_dir = trug_path.parent
if check_filesystem:
    for node in nodes:
        ntype = node.get("type", "")
        nid = node.get("id", "?")
        if ntype in ("DOCUMENT", "SPECIFICATION"):
            node_name = node.get("properties", {}).get("name", "")
            if node_name:
                file_path = folder_dir / node_name
                if not file_path.exists():
                    result.errors.append(
                        f"Node '{nid}' references file '{node_name}' "
                        f"but it does not exist in {folder_dir}"
                    )
```

---

## Warning-Level Rules

Warning-level rules have **severity = WARNING**. Warnings do **not** cause
`CheckResult.ok` to be `False` under normal operation. With `--strict` mode,
warnings are promoted to errors and cause exit code `1`.

### W-01: On-Disk Items Not in TRUG

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `W-01`                                                       |
| **Name**    | On-Disk Items Not in TRUG                                    |
| **Severity**| WARNING                                                      |
| **Description** | Files and directories in the folder that are not represented by any node's `properties.name`. Excludes items in `IGNORE_ON_DISK`, hidden files (`.`-prefixed), archived items (`zzz_`-prefixed), and `.egg-info` directories. |
| **Warning Message Template** | `On-disk item '{name}' is not represented by any node` |

```python
if check_filesystem:
    node_names: Set[str] = set()
    for node in nodes:
        name = node.get("properties", {}).get("name", "")
        if name:
            node_names.add(name)
    for item in sorted(folder_dir.iterdir()):
        if item.name in IGNORE_ON_DISK:
            continue
        if item.name.startswith("."):
            continue
        if item.name.startswith("ZZZ_"):
            continue
        if item.name.endswith(".egg-info"):
            continue
        if item.name not in node_names:
            result.warnings.append(
                f"On-disk item '{item.name}' is not represented "
                f"by any node"
            )
```

---

### W-02: Stale Flags

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `W-02`                                                       |
| **Name**    | Stale Flags                                                  |
| **Severity**| WARNING                                                      |
| **Description** | Nodes with `properties.stale` set to `true` indicate content that is known to be outdated. This warning surfaces them for human review. |
| **Warning Message Template** | `Node '{node_id}' has stale=true` |

```python
for node in nodes:
    nid = node.get("id", "?")
    props = node.get("properties", {})
    if props.get("stale") is True:
        result.warnings.append(f"Node '{nid}' has stale=true")
```

---

### W-03: Empty Contains

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **ID**      | `W-03`                                                       |
| **Name**    | Empty Contains                                               |
| **Severity**| WARNING                                                      |
| **Description** | The root FOLDER node has an empty `contains` array, meaning the TRUG does not model any children. This is technically valid but usually indicates an incomplete TRUG. |
| **Warning Message Template** | `FOLDER node '{folder_id}' has empty contains array` |

```python
if folder_node is not None:
    contains_list = folder_node.get("contains", [])
    if len(contains_list) == 0:
        result.warnings.append(
            f"FOLDER node '{folder_node.get('id', '?')}' has empty "
            f"contains array"
        )
```

---

## CLI Interface

The `folder-check` command is exposed through the `trugs` CLI and also
available as the `folder_check_command()` Python function in
`trugs_tools.cli`.

### Usage

```
trugs folder-check [PATHS...] [OPTIONS]

Arguments:
  PATHS          One or more folder.trug.json files or directories
                 If directory, looks for folder.trug.json inside it

Options:
  --all          Check all folder.trug.json files (excludes ZZZ_* dirs)
  --format       Output format: text (default), json
  --quiet        Only show summary line
  --strict       Treat warnings as errors (exit code 1)
  --root         Root directory for --all scanning (default: cwd)

Exit codes:
  0  All checks passed
  1  Errors found (or warnings in --strict mode)
  2  Runtime error
```

### Argument Resolution

| Input                          | Behavior                                              |
|--------------------------------|-------------------------------------------------------|
| `trugs folder-check foo.json`  | Check the single file `foo.json`                      |
| `trugs folder-check ./A ./B`   | Look for `folder.trug.json` in each directory         |
| `trugs folder-check --all`     | Walk cwd for all `folder.trug.json`, skip `zzz_*`    |
| `trugs folder-check --all --root /repo` | Walk `/repo` instead of cwd              |
| `trugs folder-check`  (no args, no --all) | Error: exit code 2                      |

### Option Combinations

| `--format` | `--quiet` | Effect                                               |
|------------|-----------|------------------------------------------------------|
| `text`     | no        | Full per-file output with errors, warnings, stats    |
| `text`     | yes       | Single summary line only                             |
| `json`     | no        | JSON array of result objects                         |
| `json`     | yes       | JSON array (quiet has no effect on JSON format)      |

| `--strict` | Warnings present | Exit code |
|------------|-------------------|-----------|
| no         | yes               | 0         |
| yes        | yes               | 1         |
| no         | no                | 0         |
| yes        | no                | 0         |

---

## Output Format

### Text Format (default)

Grouped by file. Errors appear first (prefixed with ❌), then warnings
(prefixed with ⚠️). A passing file with no warnings shows ✅. A summary line
follows all file results.

```
/path/to/TRUGS_TOOLS/folder.trug.json:
  Nodes: 14  Edges: 13
  ❌ Node 'bad_node': invalid type 'GENERATED' (valid: COMPONENT, ...)
  ⚠️  On-disk item 'orphan.md' is not represented by any node
  ⚠️  Node 'doc_old' has stale=true

/path/to/TRUGS_MVP/folder.trug.json:
  Nodes: 8  Edges: 7
  ✅ All checks passed

2 error(s), 2 warning(s) across 2 file(s)
```

### JSON Format (`--format json`)

An array of objects, one per file checked:

```json
[
  {
    "folder": "/path/to/TRUGS_TOOLS/folder.trug.json",
    "errors": [
      "Node 'bad_node': invalid type 'GENERATED' (valid: COMPONENT, ...)"
    ],
    "warnings": [
      "On-disk item 'orphan.md' is not represented by any node",
      "Node 'doc_old' has stale=true"
    ],
    "stats": {
      "nodes": 14,
      "edges": 13
    }
  },
  {
    "folder": "/path/to/TRUGS_MVP/folder.trug.json",
    "errors": [],
    "warnings": [],
    "stats": {
      "nodes": 8,
      "edges": 7
    }
  }
]
```

### Quiet Format (`--quiet`)

A single summary line with aggregate counts:

```
2 error(s), 2 warning(s) across 2 file(s)
```

---

## Error Message Catalog

Complete catalog of all error and warning messages produced by `folder-check`.

### Error Messages

| Rule | Code / ID | Template | Example |
|------|-----------|----------|---------|
| E-01 | `Invalid JSON` | `Invalid JSON: {detail}` | `Invalid JSON: Expecting ',' delimiter: line 5 column 3 (char 42)` |
| E-01 | `File not found` | `File not found: {path}` | `File not found: /tmp/folder.trug.json` |
| E-01 | `Not an object` | `Top-level value must be a JSON object` | — |
| E-02 | `Missing key` | `Missing required top-level key: '{key}'` | `Missing required top-level key: 'nodes'` |
| E-03 | `No folder` | `No FOLDER node with parent_id=null found` | — |
| E-03 | `Multiple folders` | `Multiple FOLDER nodes with parent_id=null: {ids}` | `Multiple FOLDER nodes with parent_id=null: root1, root2` |
| E-04 | `Invalid type` | `Node '{id}': invalid type '{type}' (valid: {list})` | `Node 'x': invalid type 'GENERATED' (valid: COMPONENT, DOCUMENT, ...)` |
| E-05 | `Wrong metric` | `Node '{id}': metric_level '{actual}' should be '{expected}' for type '{type}'` | `Node 'f': metric_level 'BASE_FOLDER' should be 'KILO_FOLDER' for type 'FOLDER'` |
| E-06 | `Bad internal rel` | `Edge '{from}' -> '{to}': invalid internal relation '{rel}' (valid: {list})` | `Edge 'a' -> 'b': invalid internal relation 'EXTENDS' (valid: contains, ...)` |
| E-07 | `Bad cross-folder rel` | `Edge '{from}' -> '{to}': invalid cross-folder relation '{rel}' (valid: {list})` | `Edge 'a' -> 'X:b': invalid cross-folder relation 'contains' (valid: ...)` |
| E-08 | `Bad syntax` | `Edge '{from}' -> '{to}': cross-folder to_id must have format 'folder_name:node_id'` | `Edge 'a' -> ':b': cross-folder to_id must have format 'folder_name:node_id'` |
| E-09 | `Contains mismatch` | `Contains-array lists '{child}' but no 'contains' edge from '{folder}' to '{child}' exists` | `Contains-array lists 'doc_x' but no 'contains' edge from 'root' to 'doc_x' exists` |
| E-10 | `Dangling from` | `Edge from_id '{id}' does not reference any node` | `Edge from_id 'ghost' does not reference any node` |
| E-10 | `Dangling to` | `Edge to_id '{id}' does not reference any node` | `Edge to_id 'missing' does not reference any node` |
| E-11 | `Missing file` | `Node '{id}' references file '{name}' but it does not exist in {dir}` | `Node 'doc_x' references file 'X.md' but it does not exist in /path/to/folder` |

### Warning Messages

| Rule | Code / ID | Template | Example |
|------|-----------|----------|---------|
| W-01 | `Orphan on disk` | `On-disk item '{name}' is not represented by any node` | `On-disk item 'orphan.md' is not represented by any node` |
| W-02 | `Stale node` | `Node '{id}' has stale=true` | `Node 'doc_old' has stale=true` |
| W-03 | `Empty contains` | `FOLDER node '{id}' has empty contains array` | `FOLDER node 'root' has empty contains array` |

---

## CheckResult API

### Class Definition

```python
class CheckResult:
    """Result of checking a single folder.trug.json file."""

    __slots__ = ("path", "errors", "warnings", "node_count", "edge_count")

    def __init__(self, path: str) -> None:
        self.path: str = path
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.node_count: int = 0
        self.edge_count: int = 0

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "folder": self.path,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "stats": {
                "nodes": self.node_count,
                "edges": self.edge_count,
            },
        }
```

### Properties

| Property       | Type         | Description                                       |
|----------------|--------------|---------------------------------------------------|
| `path`         | `str`        | Absolute path to the checked file                 |
| `errors`       | `List[str]`  | Error messages (any non-empty → `.ok` is `False`) |
| `warnings`     | `List[str]`  | Warning messages                                  |
| `node_count`   | `int`        | Number of nodes in the TRUG (0 if parse failed)   |
| `edge_count`   | `int`        | Number of edges in the TRUG (0 if parse failed)   |
| `ok`           | `bool`       | `True` if and only if `errors` is empty           |

### Methods

| Method      | Returns      | Description                                      |
|-------------|--------------|--------------------------------------------------|
| `to_dict()` | `Dict`       | Serialize to dict suitable for JSON output        |

---

## Test Matrix

The test suite contains **56 tests** across **17 test classes**, organized to
cover every rule, every branch, and every output path. All tests live in
`tests/test_folder_check.py`.

### TestValidJSON (E-01) — 3 tests

| Test                    | Scenario                               | Expected                              |
|-------------------------|----------------------------------------|---------------------------------------|
| `test_valid_json_passes`| Valid minimal TRUG                     | `result.ok == True`                   |
| `test_invalid_json_fails`| File contains `{bad json`            | Error contains `"Invalid JSON"`       |
| `test_missing_file_fails`| Path does not exist                  | Error contains `"File not found"`     |

### TestRequiredKeys (E-02) — 2 tests

| Test                        | Scenario                           | Expected                                  |
|-----------------------------|------------------------------------|-------------------------------------------|
| `test_all_keys_present_passes` | Minimal TRUG with all 7 keys   | `result.ok == True`                       |
| `test_missing_key_fails`   | `nodes` key deleted                | Error contains `"Missing required top-level key: 'nodes'"` |

### TestFolderNodeCount (E-03) — 3 tests

| Test                        | Scenario                           | Expected                                  |
|-----------------------------|------------------------------------|-------------------------------------------|
| `test_one_folder_ok`       | Single FOLDER node                 | `result.ok == True`                       |
| `test_no_folder_node`      | FOLDER changed to DOCUMENT         | Error contains `"No FOLDER node"`         |
| `test_multiple_folder_nodes`| Two FOLDER nodes with parent_id=null | Error contains `"Multiple FOLDER nodes"` |

### TestValidNodeTypes (E-04) — 9 tests

| Test                        | Scenario                           | Expected                                  |
|-----------------------------|------------------------------------|-------------------------------------------|
| `test_valid_types_pass` ×8 | Parametrized for each of 8 types   | No `"invalid type"` errors                |
| `test_invalid_type_fails`  | Node with `type="GENERATED"`       | Error contains `"invalid type 'GENERATED'"` |

### TestMetricLevels (E-05) — 2 tests

| Test                         | Scenario                          | Expected                                  |
|------------------------------|-----------------------------------|-------------------------------------------|
| `test_correct_levels_pass`  | Default minimal TRUG              | No `"metric_level"` errors                |
| `test_wrong_level_fails`    | FOLDER node with `BASE_FOLDER`    | Error contains `"metric_level 'BASE_FOLDER' should be 'KILO_FOLDER'"` |

### TestEdgeRelations (E-06, E-07) — 4 tests

| Test                               | Scenario                        | Expected                                   |
|------------------------------------|---------------------------------|--------------------------------------------|
| `test_valid_internal_relation`     | Edge with `relation="contains"` | No `"invalid internal relation"` errors    |
| `test_invalid_internal_relation`   | Edge with `relation="EXTENDS"`  | Error contains `"invalid internal relation 'EXTENDS'"` |
| `test_valid_cross_folder_relation` | Cross-folder edge with `"uses"` | No `"cross-folder"` errors                 |
| `test_invalid_cross_folder_relation`| Cross-folder edge with `"contains"` | Error contains `"invalid cross-folder relation 'contains'"` |

### TestCrossFolderSyntax (E-08) — 2 tests

| Test                                     | Scenario                       | Expected                                |
|------------------------------------------|--------------------------------|-----------------------------------------|
| `test_valid_cross_folder_syntax`        | `to_id="TRUGS_TOOLS:comp_validator"` | No `"folder_name:node_id"` errors |
| `test_invalid_cross_folder_syntax_empty_parts` | `to_id=":node_only"`    | Error contains `"folder_name:node_id"`  |

### TestContainsConsistency (E-09) — 2 tests

| Test                        | Scenario                           | Expected                                  |
|-----------------------------|------------------------------------|-------------------------------------------|
| `test_consistent_contains` | Contains array + matching edge     | No `"Contains-array"` errors              |
| `test_missing_contains_edge`| Contains array, no edge           | Error contains `"Contains-array lists 'doc_readme'"` |

### TestDanglingEdges (E-10) — 4 tests

| Test                              | Scenario                         | Expected                                    |
|-----------------------------------|----------------------------------|---------------------------------------------|
| `test_valid_edge_refs`           | Both endpoints exist             | No `"does not reference any node"` errors   |
| `test_dangling_from_id`         | `from_id="ghost_node"`           | Error contains `"from_id 'ghost_node' does not reference"` |
| `test_dangling_to_id`           | `to_id="missing_node"`           | Error contains `"to_id 'missing_node' does not reference"` |
| `test_cross_folder_to_id_not_dangling` | `to_id="OTHER:some_node"` | No dangling errors (cross-folder exempt)    |

### TestFilesystemExistence (E-11) — 3 tests

| Test                       | Scenario                            | Expected                                  |
|----------------------------|-------------------------------------|-------------------------------------------|
| `test_existing_file_passes`| `README.md` exists on disk          | No `"does not exist"` errors              |
| `test_missing_file_fails`  | DOCUMENT node, file absent          | Error contains `"does not exist"`         |
| `test_spec_file_missing`   | SPECIFICATION node, file absent     | Error contains `"does not exist"`         |

### TestWarnings (W-01, W-02, W-03) — 4 tests

| Test                            | Scenario                         | Expected                                  |
|---------------------------------|----------------------------------|-------------------------------------------|
| `test_on_disk_not_in_trug`     | `orphan_file.md` on disk         | Warning contains `"orphan_file.md"`       |
| `test_stale_flag_warning`      | Node with `stale=true`           | Warning contains `"stale=true"`           |
| `test_empty_contains_warning`  | FOLDER with `contains=[]`        | Warning contains `"empty contains"`       |
| `test_non_empty_contains_no_warning` | FOLDER with children        | No `"empty contains"` warnings            |

### TestFindAllFolderTrugs — 2 tests

| Test                | Scenario                              | Expected                                  |
|---------------------|---------------------------------------|-------------------------------------------|
| `test_finds_files`  | Two subdirs each with folder.trug.json | `len(found) == 2`                        |
| `test_excludes_zzz` | One normal dir + one `zzz_ARCHIVE`    | `len(found) == 1`, no ZZZ in path         |

### TestCheckAll — 3 tests

| Test                      | Scenario                          | Expected                                |
|---------------------------|-----------------------------------|-----------------------------------------|
| `test_scan_all`          | `scan_all=True` with one subdir   | 1 result, `.ok == True`                 |
| `test_explicit_paths_file`| Pass explicit file path           | 1 result                                |
| `test_explicit_paths_dir` | Pass directory path               | 1 result (finds `folder.trug.json`)     |

### TestFormatText — 2 tests

| Test                | Scenario            | Expected                                       |
|---------------------|---------------------|------------------------------------------------|
| `test_quiet_mode`  | `quiet=True`        | Output contains `"0 error(s)"` and `"1 file(s)"` |
| `test_verbose_mode`| `quiet=False`       | Output contains `"Nodes:"` and `"Edges:"`      |

### TestFormatJSON — 1 test

| Test                   | Scenario          | Expected                                          |
|------------------------|-------------------|---------------------------------------------------|
| `test_valid_json_output`| Single result    | Parses as list, has `folder`, `errors`, `warnings`, `stats` |

### TestCLI — 7 tests

| Test                          | Scenario                         | Expected                                |
|-------------------------------|----------------------------------|-----------------------------------------|
| `test_check_single_file`    | Valid file                       | Exit code `0`                           |
| `test_check_with_errors`    | Invalid node type                | Exit code `1`                           |
| `test_json_format`          | `--format json`                  | stdout parses as JSON list              |
| `test_quiet_mode`           | `--quiet`                        | stdout contains `"error(s)"`            |
| `test_strict_mode_warnings` | `--strict` + empty contains      | Exit code `1` (warnings → errors)       |
| `test_all_flag`             | `--all --root <tmpdir>`          | Exit code `0`                           |
| `test_no_args_returns_error`| No arguments, no `--all`         | `SystemExit` with code `2`              |

### TestCheckResult — 3 tests

| Test                   | Scenario              | Expected                                       |
|------------------------|-----------------------|------------------------------------------------|
| `test_ok_when_no_errors`| Fresh CheckResult    | `.ok == True`                                  |
| `test_not_ok_with_errors`| After appending error | `.ok == False`                                |
| `test_to_dict`         | With errors + warnings | Dict has correct `folder`, `errors`, `warnings`, `stats` |

### Test Summary

| Category            | Classes | Tests |
|---------------------|---------|-------|
| Error rules (E-01–E-11) | 11  | 34    |
| Warning rules (W-01–W-03) | 1  | 4     |
| Multi-file scanning | 2       | 5     |
| Output formatting   | 2       | 3     |
| CLI                 | 1       | 7     |
| CheckResult         | 1       | 3     |
| **Total**           | **17**  | **56** |

---

## Integration with Governance Spec

The governance constants (`VALID_NODE_TYPES`, `VALID_INTERNAL_RELATIONS`,
`VALID_CROSS_FOLDER_RELATIONS`, `REQUIRED_TOP_LEVEL_KEYS`) are currently
**hardcoded** at module scope in `folder_check.py`. They are derived from the
authoritative specification in
[TRUGS_FILES/SPEC_folder_governance.md](../TRUGS_FILES/SPEC_folder_governance.md).

### Current Approach: Hardcoded Constants

**Rationale:**

- Zero-dependency design — no file I/O or parsing needed at import time.
- Test determinism — constants are frozen and version-controlled.
- Speed — no runtime loading overhead.

**Trade-off:**

- When `SPEC_folder_governance.md` is updated, the constants in
  `folder_check.py` must be manually synchronized.

### Future Approach: governance.json Loading

A planned enhancement will allow the checker to load governance constants from
a machine-readable `governance.json` file at runtime:

```python
# Future: load from governance.json
def load_governance(path: Path) -> GovernanceSpec:
    with open(path) as f:
        data = json.load(f)
    return GovernanceSpec(
        valid_node_types=data["valid_node_types"],
        valid_internal_relations=set(data["valid_internal_relations"]),
        valid_cross_folder_relations=set(data["valid_cross_folder_relations"]),
        required_top_level_keys=set(data["required_top_level_keys"]),
    )
```

Until `governance.json` exists, the hardcoded constants are the single source
of truth for the checker.

---

## Future Extensions

The following features are **not** implemented in v1.0 but are planned or
under consideration for future releases.

### governance.json Loading

- Machine-readable governance constants loaded from
  `TRUGS_FILES/governance.json`.
- `folder-check` will accept a `--governance` flag to override the default
  path.
- Enables governance updates without modifying Python source code.

### W-04: Phase / Status Drift

- Compare the `properties.phase` and `properties.status` fields of nodes
  against the current state documented in `AAA.md`.
- Not yet implemented because AAA.md is a prose document with no
  machine-readable schema. Requires an AAA.md parser or structured metadata
  field.

### GitHub Action Integration

- A reusable GitHub Action that runs `trugs folder-check --all --strict` on
  every PR.
- Produces SARIF output for GitHub Code Scanning integration.
- Blocks merges when folder TRUGs have governance errors.

### Additional Planned Improvements

| Feature                  | Description                                          |
|--------------------------|------------------------------------------------------|
| `--fix` mode             | Automatically repair common errors (wrong metric_level, missing contains edges) |
| SARIF output             | Standard format for security/quality tools           |
| Watch mode               | Re-run checks on file changes (`--watch`)            |
| Cross-folder resolution  | Verify cross-folder `to_id` references actually exist in target TRUGs |
| Parallel checking        | Use `concurrent.futures` for large repositories      |

---

## Dependencies

### Runtime

- Python 3.8+
- Standard library only: `json`, `os`, `re`, `pathlib`, `typing`

### Testing

- `pytest`
- `pytest-cov` (for coverage reporting)

### CLI

- `argparse` (stdlib) — used by `folder_check_command()` in `trugs_tools.cli`

---

## References

- [TRUGS_FILES/SPEC_folder_governance.md](../TRUGS_FILES/SPEC_folder_governance.md) — Authoritative governance specification
- [TRUGS_PROTOCOL/TRUGS_CORE.md](../TRUGS_PROTOCOL/TRUGS_CORE.md) — CORE structure specification
- [TRUGS_TOOLS/SPEC_validator.md](SPEC_validator.md) — TRUGS Validator specification (sibling tool)
- [TRUGS_TOOLS/SPEC_cli.md](SPEC_cli.md) — CLI framework specification
- [AAA.md](AAA.md) — TRUGS_TOOLS project overview

---

## Specification Status

✅ **Complete** — Implementation matches this specification. All 56 tests pass.

**Implementation files:**
- `trugs_tools/filesystem/folder_check.py` — Core validation logic
- `trugs_tools/cli.py` — CLI entry point (`folder_check_command`)
- `tests/test_folder_check.py` — Complete test suite (56 tests)
