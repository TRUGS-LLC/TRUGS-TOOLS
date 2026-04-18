# SPEC_folder_init.md — `trugs folder-init` Specification

**Version:** 1.0.0  
**Status:** ACTIVE  
**Last Updated:** 2026-02-22

---

> **Implementation note (2026-03-20):** This command now uses `trugs-store`
> (`InMemoryGraphStore` + `JsonFilePersistence`) internally for all graph I/O.
> The bidirectional invariant (parent.contains ↔ child.parent_id ↔ CONTAINS edge)
> is enforced automatically by the store. See `TRUGS_STORE/SPEC_844_graphstore_protocol.py`.


## Purpose

`trugs folder-init` automates the creation of skeleton `folder.trug.json` files by scanning a folder's filesystem. It generates nodes (FOLDER, DOCUMENT, SPECIFICATION, COMPONENT, TEST_SUITE, EXAMPLE_SET, SCHEMA, TEMPLATE) and mechanical edges (`contains`, `tests`). The human then curates additional edges and enriches descriptions.

**Design Philosophy:** Generate what the filesystem proves; leave intent to humans.

---

## Architecture

### Design Principles

1. **Filesystem is ground truth** — every count, filename, and structural decision comes from `os.walk`, `Path.glob`, or similar filesystem calls.
2. **Zero runtime dependencies** — only Python stdlib (`json`, `pathlib`, `datetime`, `re`, `os`, `subprocess`, `typing`).
3. **Modular scanners** — each node type has a dedicated scanner function that can be tested in isolation.
4. **Mechanical edges only** — only `contains` (FOLDER→child) and `tests` (TEST_SUITE→COMPONENT) edges are generated. All others require human curation.

### Module Structure

```
trugs_tools/filesystem/folder_init.py
├── init_folder_trug(path, force, run_tests) → dict    # Main entry point
├── _scan_documents(folder_path) → List[dict]           # SC-01 + SC-02
├── _scan_components(folder_path) → List[dict]          # SC-03
├── _scan_tests(folder_path, run_tests) → Optional[dict]# SC-04
├── _scan_schemas(folder_path) → Optional[dict]         # SC-05
├── _scan_templates(folder_path) → Optional[dict]       # SC-06
├── _scan_examples(folder_path) → Optional[dict]        # SC-07
├── _read_aaa_metadata(folder_path) → dict              # SC-08
├── _read_pyproject_metadata(folder_path) → dict        # SC-09
├── _make_node_id(prefix, name) → str                   # ID generation
├── _build_edges(folder_id, nodes) → List[dict]         # Edge builder
└── _count_lines(path) → int                            # LOC counter
```

### Scanning Pipeline

1. Create root FOLDER node
2. Run all scanners → collect child nodes
3. Populate FOLDER `contains` array with child IDs
4. Build mechanical edges (`contains` + `tests`)
5. Assemble top-level TRUG dict
6. Return dict (caller writes to disk)

---

## Scanners

### SC-01: Document Scanner

- **Source:** All `*.md` files in the folder root (non-recursive)
- **Detection rule:** `Path(folder_path).glob("*.md")`
- **Node type:** `DOCUMENT` with `metric_level: "BASE_DOCUMENT"`
- **Properties:** `name` (filename), `purpose` (inferred from filename), `format: "markdown"`
- **ID convention:** `doc_{stem_lower}` (e.g., `doc_readme` for README.md)
- **Edge case:** If no `.md` files, returns empty list
- **Exclusion:** Files matching `SPEC_*.md` are handled by SC-02 instead

### SC-02: Specification Scanner

- **Source:** `*.md` files matching `SPEC_*.md` in folder root
- **Detection rule:** Regex `r'^SPEC_.*\.md$'` (case-insensitive)
- **Node type:** `SPECIFICATION` with `metric_level: "BASE_SPECIFICATION"`
- **Properties:** `name` (filename), `purpose` (inferred from filename), `format: "markdown"`
- **ID convention:** `spec_{stem_lower}` (e.g., `spec_folder_check` for SPEC_folder_check.md)
- **Edge case:** Handled as subset of document scanning in `_scan_documents`

### SC-03: Component Scanner

- **Source:** Subdirectories of folder root containing ≥1 `.py` file
- **Detection rule:** `any(d.glob("*.py"))` for each subdirectory
- **Skip list:** `tests/`, `__pycache__/`, `.git/`, `node_modules/`, `htmlcov/`, `EXAMPLES/`, `examples/`, `.pytest_cache/`, `.mypy_cache/`, `.tox/`, `.eggs/`, `dist/`, `build/`
- **Node type:** `COMPONENT` with `metric_level: "DEKA_COMPONENT"`
- **Properties:** `name` (directory name), `purpose` (from directory name), `file_count` (`.py` files, recursive), `loc` (total lines across all `.py` files)
- **ID convention:** `comp_{dirname_lower}` (e.g., `comp_trugs_tools` for trugs_tools/)
- **Edge case:** If no qualifying subdirectories, returns empty list

### SC-04: Test Suite Scanner

- **Source:** `tests/` directory in folder root
- **Detection rule:** `(folder_path / "tests").is_dir()`
- **Node type:** `TEST_SUITE` with `metric_level: "BASE_TEST_SUITE"`
- **Properties:** `name: "tests/"`, `test_files` (count of `test_*.py` + `*_test.py` files), `test_count` (from pytest if `run_tests=True`, else from file count)
- **ID convention:** `test_suite`
- **Edge case:** Returns `None` if no `tests/` directory
- **Subprocess:** If `run_tests=True`, runs `pytest --co -q` to count tests. On failure/timeout, falls back to file count.

### SC-05: Schema Scanner

- **Source:** `schemas/` directory or `*.schema.json` files in folder root
- **Detection rule:** `(folder_path / "schemas").is_dir()` or `list(folder_path.glob("*.schema.json"))`
- **Node type:** `SCHEMA` with `metric_level: "BASE_SCHEMA"`
- **Properties:** `name` (directory or "schemas"), `schema_count` (number of schema files)
- **ID convention:** `schema_set`
- **Edge case:** Returns `None` if neither condition met

### SC-06: Template Scanner

- **Source:** `templates/` directory in folder root
- **Detection rule:** `(folder_path / "templates").is_dir()`
- **Node type:** `TEMPLATE` with `metric_level: "BASE_TEMPLATE"`
- **Properties:** `name: "templates/"`, `template_count` (file count in templates/)
- **ID convention:** `template_set`
- **Edge case:** Returns `None` if no `templates/` directory

### SC-07: Example Set Scanner

- **Source:** `EXAMPLES/` or `examples/` directory in folder root
- **Detection rule:** Either `(folder_path / "EXAMPLES").is_dir()` or `(folder_path / "examples").is_dir()`
- **Node type:** `EXAMPLE_SET` with `metric_level: "BASE_EXAMPLE_SET"`
- **Properties:** `name` (actual directory name), `example_count` (file count in directory)
- **ID convention:** `example_set`
- **Edge case:** Returns `None` if neither directory exists. Prefers `EXAMPLES/` if both exist.

### SC-08: AAA.md Metadata Reader

- **Source:** `AAA.md` in folder root
- **Detection rule:** `(folder_path / "AAA.md").exists()`
- **Extraction:** Regex for `**Phase:**`, `**Status:**`, `**Version:**` lines
- **Output:** `{"phase": ..., "status": ..., "version": ...}` (only present keys)
- **Edge case:** Returns empty dict if no AAA.md or no matching lines
- **Rule:** NEVER use AAA.md for file counts, structure, or component inventory

### SC-09: pyproject.toml Metadata Reader

- **Source:** `pyproject.toml` in folder root
- **Detection rule:** `(folder_path / "pyproject.toml").exists()`
- **Extraction:** Simple line parsing for `name`, `version`, `description`
- **Output:** `{"name": ..., "version": ..., "description": ...}` (only present keys)
- **Edge case:** Returns empty dict if no pyproject.toml
- **Rule:** NO `tomli` or `toml` dependency — stdlib line parsing only

---

## Node Generation

### FOLDER Node

Every generated TRUG has exactly one FOLDER node with `parent_id: null`:

```json
{
  "id": "{folder_name_lower}_folder",
  "type": "FOLDER",
  "properties": {
    "name": "FOLDER_NAME",
    "purpose": "...",
    "phase": "...",
    "status": "...",
    "version": "..."
  },
  "parent_id": null,
  "contains": ["child_id_1", "child_id_2"],
  "metric_level": "KILO_FOLDER",
  "dimension": "folder_structure"
}
```

### Edge Generation

Only two types of edges are generated:

1. **`contains` edges:** FOLDER → every child node
2. **`tests` edges:** TEST_SUITE → each COMPONENT (if both exist)

```json
{
  "from_id": "folder_id",
  "to_id": "child_id",
  "relation": "contains",
  "weight": 1.0
}
```

### ID Naming Convention

- Snake_case, lowercase
- Prefix by node type: `doc_`, `spec_`, `comp_`, `test_`, `schema_`, `template_`, `example_`
- Derived from filename stem or directory name
- Special: FOLDER uses `{folder_name_lower}_folder`, TEST_SUITE uses `test_suite`

---

## CLI Interface

### Usage

```
trugs folder-init PATH              Generate folder.trug.json for one folder
trugs folder-init --all             Generate for all folders missing folder.trug.json
trugs folder-init PATH --dry-run    Print to stdout instead of writing file
trugs folder-init PATH --force      Overwrite existing folder.trug.json
trugs folder-init PATH --no-tests   Skip pytest test count (faster, no subprocess)
trugs folder-init --all --root DIR  Scan from specific root directory
```

### Options

| Option | Description |
|--------|-------------|
| `PATH` | Target folder path |
| `--all` | Generate for all folders missing folder.trug.json |
| `--dry-run` | Print JSON to stdout, don't write file |
| `--force` | Overwrite existing folder.trug.json |
| `--no-tests` | Skip pytest subprocess for test counting |
| `--root DIR` | Root directory for `--all` scanning (default: cwd) |

### Output Behavior

- **Default:** Writes `folder.trug.json` to target folder, prints path to stdout
- **`--dry-run`:** Prints formatted JSON to stdout, does not write
- **`--all`:** Processes each qualifying folder, prints summary

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | folder.trug.json already exists (without --force) or invalid path |
| 2 | Write error |

---

## Test Strategy

### Test Fixtures

Tests use `tempfile.mkdtemp()` to create isolated folder structures. Each test creates only the files/directories needed for the scanner under test.

### Comparison Rules

Generated TRUGs are validated for:
1. Correct node types present
2. Correct node counts
3. Passes `trugs-validate`
4. Correct `contains` array on FOLDER node
5. Correct mechanical edges

Generated TRUGs are NOT compared byte-for-byte with hand-built TRUGs (hand-built have human-curated edges and enriched descriptions).
