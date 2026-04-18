# TRUGS_TOOLS: Frequently Asked Questions

---

## Getting Started

### Q: What is TRUGS and what are TRUG files?

TRUGS stands for **Tree-Relational Unified Graph Structures** — a protocol for representing code, knowledge, and content as directed graphs. A TRUG file is a JSON document (`.trug.json`) containing typed **nodes**, directed **edges**, **dimensions**, and **capabilities**. Every node has 7 required fields (`id`, `type`, `properties`, `parent_id`, `contains`, `metric_level`, `dimension`) and every edge has 3 (`from_id`, `to_id`, `relation`). TRUGS_TOOLS is the Python toolchain for creating, validating, rendering, and managing these files.

### Q: How do I install TRUGS_TOOLS?

Install from source in editable mode (Python 3.8+ required, zero runtime dependencies):

```bash
cd TRUGS_TOOLS
pip install -e .
```

For development with test dependencies:

```bash
pip install -e ".[test]"
```

Verify the installation:

```bash
trugs --version
# trugs-tools 1.0.0 (AAA_AARDVARK)
```

### Q: What is a branch?

A branch defines the **vocabulary and node types** for a specific domain. TRUGS v1.0 supports 10 branches:

| Branch | Domain |
|--------|--------|
| Python | Python source code |
| Rust | Rust source code |
| LLVM | LLVM IR representation |
| Web | HTML/CSS/JS web projects |
| Writer | Prose and documentation |
| Semantic | Meaning and concept graphs |
| Orchestration | Workflow and pipeline graphs |
| Living | Evolving/versioned graphs |
| Knowledge | Knowledge base graphs |
| Executable | Runnable program graphs |

Each branch has its own node type vocabulary and template (minimal and complete).

### Q: What are metric levels and how do they work?

Metric levels use **SI prefix format** (`{PREFIX}_{SEMANTIC_NAME}`) to express the granularity of a node in the graph hierarchy. A parent's metric level must always be ≥ its child's level. Common levels:

| Level | Scale | Typical Use |
|-------|-------|-------------|
| `MEGA_ROOT` | 10⁶ | Project root |
| `KILO_SPEC` | 10³ | Specification / package |
| `DEKA_MODULE` | 10¹ | Module / file |
| `BASE_FUNCTION` | 10⁰ | Function / class |
| `CENTI_DOC` | 10⁻² | Documentation block |
| `MILLI_STATEMENT` | 10⁻³ | Individual statement |
| `MICRO_EXPRESSION` | 10⁻⁶ | Expression / token |

---

## Validation

### Q: What are the 9 validation rules?

The validator enforces these rules in order:

| Rule | Check | Error Code |
|------|-------|------------|
| 1 | Node IDs must be unique | `DUPLICATE_NODE_ID` |
| 2 | `parent_id` ↔ `contains` consistency | `PARENT_MISSING_CONTAINS` |
| 3 | No self-containment cycles | `SELF_CONTAINMENT_CYCLE` |
| 4 | TRUG must have an `edges` array | `MISSING_EDGES_ARRAY` |
| 5 | Edge `from_id`/`to_id` reference valid nodes | `INVALID_FROM_ID` / `INVALID_TO_ID` |
| 6 | Nodes have required fields (`id`, `type`, `metric_level`) | `MISSING_NODE_FIELD` |
| 7 | Edges have required fields (`from_id`, `to_id`, `relation`) | `MISSING_EDGE_FIELD` |
| 8 | Extensions are valid | `INVALID_EXTENSION` |
| 9 | `metric_level` follows `{SI_PREFIX}_{NAME}` format | `INVALID_METRIC_LEVEL` |

### Q: How do I validate a TRUG file?

**CLI:**

```bash
# Single file
tg validate my_trug.json

# Multiple files
tg validate file1.json file2.json

# JSON output for scripting
tg validate --format json my_trug.json

# Quiet mode (exit code only)
tg validate --quiet my_trug.json && echo "Valid"
```

**Python API:**

```python
from trugs_tools import validate_trug

result = validate_trug("my_trug.json")
if result.valid:
    print("✓ Valid")
else:
    for error in result.errors:
        print(error)
```

You can also pass a `dict` directly instead of a file path.

### Q: What are the most common validation errors and how do I fix them?

**1. `PARENT_MISSING_CONTAINS`** — A node's `parent_id` points to a parent that doesn't list it in `contains[]`.
Fix: Add the child's ID to the parent's `contains` array.

**2. `INVALID_METRIC_LEVEL`** — The `metric_level` value isn't in `{SI_PREFIX}_{NAME}` format.
Fix: Use a valid SI prefix like `BASE_FUNCTION`, not `function` or `FUNCTION`.

**3. `INVALID_FROM_ID` / `INVALID_TO_ID`** — An edge references a node ID that doesn't exist.
Fix: Check for typos in `from_id`/`to_id` or add the missing node.

**4. `DUPLICATE_NODE_ID`** — Two or more nodes share the same `id`.
Fix: Give each node a unique identifier.

### Q: What are the CLI exit codes for validation?

| Exit Code | Meaning |
|-----------|---------|
| 0 | All files valid |
| 1 | Validation errors found |
| 2 | File not found, read error, or invalid JSON |

---

## Generation

### Q: How do I generate a TRUG file?

**CLI:**

```bash
# Minimal Python TRUG (3 nodes)
tg generate --branch python --template minimal --output example.json

# Complete Rust TRUG with extensions
tg generate --branch rust --template complete --extension typed --extension ownership --output rust.json

# Generate all branches at once
tg generate --all --output-dir examples/
```

**Python API:**

```python
from trugs_tools import generate_trug

# Minimal TRUG
trug = generate_trug("python", template="minimal")

# With extensions
trug = generate_trug("python", extensions=["typed", "scoped"])
```

All generated TRUGs are **valid by construction** — they pass all 9 validation rules automatically.

### Q: What templates and extensions are available?

**Templates:**

| Template | Description |
|----------|-------------|
| `minimal` | 3–5 nodes demonstrating basic structure |
| `complete` | 20–50 nodes demonstrating full branch patterns |

**Extensions** (can be combined with any branch):

| Extension | Adds |
|-----------|------|
| `typed` | Type annotations on nodes |
| `scoped` | Scope/visibility metadata |
| `ownership` | Ownership and borrowing (Rust-oriented) |
| `lifetime` | Lifetime annotations |
| `ssa` | Static Single Assignment form |

```bash
tg generate --branch python --extension typed --extension scoped
```

---

## Rendering

### Q: What is `folder.trug.json` and how does it work?

`folder.trug.json` is a special TRUG file that describes a **project directory** as a graph. It tracks every file as a node with typed edges between them (e.g., `DEPENDS_ON`, `TESTS`, `DOCUMENTS`). The renderer compiles this file into three deterministic markdown files:

| Output | Audience |
|--------|----------|
| `AAA.md` | Developers + LLMs — 8-phase development tracker |
| `README.md` | Humans — orientation and contents |
| `ARCHITECTURE.md` | LLMs + Architects — full node/edge details |

### Q: How do I render documentation from a `folder.trug.json`?

```bash
# Render all three files
tg render folder.trug.json

# Preview without writing
tg render folder.trug.json --dry-run

# Render only ARCHITECTURE.md
tg render folder.trug.json --file-type architecture

# Output to a different directory
tg render folder.trug.json -o /tmp/output
```

**Python API:**

```python
from trugs_tools.renderer import render_all

results = render_all(trug_dict)
# {"AAA.md": "...", "README.md": "...", "ARCHITECTURE.md": "..."}
```

### Q: Is the rendering deterministic? Can I edit the generated files?

**Yes, rendering is fully deterministic.** The same `folder.trug.json` input always produces byte-identical output. There is no LLM or inference involved — it's a pure template engine.

**No, do not edit the generated files.** All rendered files include the marker `<!-- GENERATED BY TRUGS — DO NOT EDIT -->`. Changes will be overwritten on the next render. Instead, edit the `folder.trug.json` source and re-render.

---

## Filesystem Commands

### Q: How do I initialize a project and add files?

```bash
# Initialize with auto-discovery
trugs tinit . -n "My Project" --scan

# Manually add files (type is inferred from extension)
trugs tadd main.py utils.py
trugs tadd data.csv -t CONFIGURATION

# Create typed edges
trugs tlink main_py utils_py -r DEPENDS_ON
trugs tlink test_py main_py -r TESTS

# Render docs from the graph
trugs twatch . --once
```

File extensions are mapped automatically: `.py` → `SOURCE`, `.md` → `DOCUMENT`, `.json` → `CONFIGURATION`, `.test.py` → `TEST`.

### Q: How do I keep the graph in sync with the filesystem?

Use `tsync` to discover new files, detect removed ones, and optionally infer edges from imports:

```bash
# Full sync
trugs tsync .

# Preview changes without modifying
trugs tsync . --dry-run

# Sync files only (skip edge inference)
trugs tsync . --no-edges
```

For continuous synchronization during development, use the watcher:

```bash
trugs twatch .              # Watch and auto-regenerate docs
trugs twatch . --interval 5 # Check every 5 seconds
```

### Q: What edge relation types are available for `tlink`?

The following relations are valid:

`CONFIGURES`, `CONTAINS`, `DEPENDS_ON`, `DOCUMENTS`, `EXTENDS`, `GENERATES`, `IMPLEMENTS`, `ORCHESTRATES`, `REFERENCES`, `RENDERS`, `TESTS`, `VALIDATES`

```bash
trugs tlink main_py utils_py -r DEPENDS_ON
trugs tlink readme_md main_py -r DOCUMENTS
trugs tlink main_py utils_py -r DEPENDS_ON --remove  # Remove an edge
```

---

## Troubleshooting

### Q: I get `INVALID_METRIC_LEVEL` — what format does `metric_level` need?

`metric_level` must follow the format `{SI_PREFIX}_{SEMANTIC_NAME}` where both parts are UPPERCASE. The SI prefix must be one of the 21 standard prefixes.

**Wrong:**
```json
{"metric_level": "function"}
{"metric_level": "base_function"}
{"metric_level": "FUNCTION"}
```

**Correct:**
```json
{"metric_level": "BASE_FUNCTION"}
{"metric_level": "MILLI_STATEMENT"}
{"metric_level": "MEGA_ROOT"}
```

Valid SI prefixes: `YOTTA`, `ZETTA`, `EXA`, `PETA`, `TERA`, `GIGA`, `MEGA`, `KILO`, `HECTO`, `DEKA`, `BASE`, `DECI`, `CENTI`, `MILLI`, `MICRO`, `NANO`, `PICO`, `FEMTO`, `ATTO`, `ZEPTO`, `YOCTO`.

### Q: I get `INVALID_FROM_ID` or `INVALID_TO_ID` — how do I fix edge reference errors?

These errors mean an edge references a node ID that doesn't exist in the `nodes` array. Common causes:

1. **Typo in node ID** — Check `from_id`/`to_id` spelling against your nodes' `id` fields.
2. **Deleted node** — You removed a node but left edges pointing to it.
3. **ID mismatch** — The filesystem commands generate IDs from filenames (e.g., `main.py` → `main_py`). Verify the generated ID matches.

```bash
# Find all node IDs in your graph
trugs tfind -C . -f json | python -c "import sys,json; [print(n['id']) for n in json.load(sys.stdin)]"
```

### Q: I get `FileNotFoundError` when running filesystem commands — what's wrong?

Filesystem commands require a `folder.trug.json` to exist in the target directory. Initialize one first:

```bash
trugs tinit .          # Create folder.trug.json
trugs tinit . --scan   # Create and auto-discover files
```

If you already have a `folder.trug.json`, make sure you're running the command in the right directory or use the `-C` flag:

```bash
trugs tadd main.py -C /path/to/project
trugs tls /path/to/project
```

### Q: Validation passes but my TRUG doesn't look right — what else should I check?

The validator checks **structural correctness** (the 9 rules), but does not check:

- **Node type vocabularies** — Branch-specific types (e.g., `FUNCTION` vs `METHOD`) are not validated.
- **Property schemas** — The `properties` object is open and unchecked.
- **Domain semantics** — Whether your graph makes logical sense for your use case.

Use `tg info` to inspect your graph's structure and catch issues visually:

```bash
tg info my_trug.json
```

This shows node type distributions, edge relation counts, hierarchy depth, and other statistics that can reveal structural problems the validator won't catch.
