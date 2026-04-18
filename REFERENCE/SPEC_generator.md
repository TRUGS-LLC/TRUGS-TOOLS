# TRUGS_TOOLS: Generator Specification

**Version:** 1.0.0 (AAA_AARDVARK)
**Component:** TRUGS_TOOLS Generator
**Status:** ✅ Specification Complete
**Last Updated:** 2026-02-10
**Parent:** [AAA.md](AAA.md)

---

## Purpose

The TRUGS Generator is a Python library and CLI tool that creates example TRUG files for all 6 branches (Python, Rust, LLVM, Web, Writer, Semantic) and 5 extensions (typed, ssa, control_flow, scoped, ownership).

**What it generates:**
- ✅ Minimal valid TRUGs (3-5 nodes, demonstrating structure)
- ✅ Complete example TRUGs (20-50 nodes, demonstrating patterns)
- ✅ Branch-specific vocabularies and properties
- ✅ Extension-specific capabilities
- ✅ Proper hierarchy and metric levels
- ✅ Valid CORE structure (passes all 9 validation rules)

**Primary Use Cases:**
1. **Documentation Examples** - Generate examples for TRUGS_PROTOCOL docs
2. **Testing** - Create test fixtures for validators and tools
3. **Templates** - Provide starting points for users creating TRUGs
4. **Validation** - Prove specification is implementable

---

## Architecture

### Design Principles

1. **Template-Based** - Each branch has minimal + complete templates
2. **Composable** - Extensions can be added to any branch
3. **Valid by Construction** - Generated TRUGs always pass validation
4. **Readable Output** - Pretty-printed JSON with comments (as properties)
5. **Deterministic** - Same inputs always produce same output

### Module Structure

```
trugs_tools/
├── generator.py          # Main generator API
├── templates/            # Branch templates
│   ├── __init__.py
│   ├── python.py         # Python branch templates
│   ├── rust.py           # Rust branch templates
│   ├── llvm.py           # LLVM branch templates
│   ├── web.py            # Web branch templates
│   ├── writer.py         # Writer branch templates
│   └── semantic.py       # Semantic branch templates
└── extensions.py         # Extension property generators
```

### Generation Pipeline

```
Input: Branch name + Extensions + Template type
  ↓
1. Load Branch Template (minimal or complete)
  ↓
2. Generate Base TRUG (nodes, edges, dimensions)
  ↓
3. Apply Extensions (add extension properties)
  ↓
4. Validate Output (ensure CORE compliance)
  ↓
5. Format JSON (pretty-print with indentation)
  ↓
Output: Valid TRUG JSON
```

---

## Branch Templates

### Python Branch

**Node Types:** MODULE, CLASS, FUNCTION, STATEMENT, EXPRESSION
**Edge Relations:** CONTAINS, CALLS, IMPORTS, DEFINES
**Primary Dimension:** code_structure
**Common Extensions:** typed, scoped

#### Minimal Template (3 nodes)

```python
def generate_python_minimal() -> dict:
    """Generate minimal Python TRUG.
    
    Structure:
    - 1 MODULE (root)
    - 1 FUNCTION
    - 1 STATEMENT
    """
    return {
        "name": "Python Minimal Example",
        "version": "1.0.0",
        "type": "CODE",
        "dimensions": {
            "code_structure": {
                "description": "Python code hierarchy",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["python_3.12"],
            "profiles": []
        },
        "nodes": [
            {
                "id": "module_main",
                "type": "MODULE",
                "properties": {
                    "module_name": "main",
                    "docstring": "Main module"
                },
                "parent_id": None,
                "contains": ["func_greet"],
                "metric_level": "DEKA_MODULE",
                "dimension": "code_structure"
            },
            {
                "id": "func_greet",
                "type": "FUNCTION",
                "properties": {
                    "function_name": "greet",
                    "parameters": ["name"],
                    "docstring": "Greet someone"
                },
                "parent_id": "module_main",
                "contains": ["stmt_return"],
                "metric_level": "BASE_FUNCTION",
                "dimension": "code_structure"
            },
            {
                "id": "stmt_return",
                "type": "STATEMENT",
                "properties": {
                    "statement_type": "return",
                    "code": "return f'Hello, {name}!'"
                },
                "parent_id": "func_greet",
                "contains": [],
                "metric_level": "CENTI_STATEMENT",
                "dimension": "code_structure"
            }
        ],
        "edges": []
    }
```

#### Complete Template (20+ nodes)

```python
def generate_python_complete() -> dict:
    """Generate complete Python TRUG.
    
    Structure:
    - 1 MODULE (root)
    - 2 CLASSes
    - 4 FUNCTIONs (2 methods, 2 module-level)
    - 12 STATEMENTs
    - Edges: CALLS, IMPORTS, DEFINES
    """
    # See BRANCH_SPECS/python.md for full template
```

**Properties:**
- `module_name` - Module identifier
- `class_name` - Class identifier
- `function_name` - Function identifier
- `parameters` - List of parameter names
- `docstring` - Documentation string
- `statement_type` - Type of statement (return, assign, call, etc.)
- `code` - Source code snippet (optional)

---

### Rust Branch

**Node Types:** CRATE, MODULE, STRUCT, FUNCTION, STATEMENT, EXPRESSION
**Edge Relations:** CONTAINS, CALLS, USES, IMPLEMENTS, BORROWS
**Primary Dimension:** code_structure
**Common Extensions:** ownership, typed, scoped

#### Minimal Template (3 nodes)

```python
def generate_rust_minimal() -> dict:
    """Generate minimal Rust TRUG.
    
    Structure:
    - 1 MODULE (root)
    - 1 FUNCTION
    - 1 STATEMENT
    """
    return {
        "name": "Rust Minimal Example",
        "version": "1.0.0",
        "type": "CODE",
        "dimensions": {
            "code_structure": {
                "description": "Rust code hierarchy",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": ["ownership"],  # Rust requires ownership
            "vocabularies": ["rust_1.75"],
            "profiles": []
        },
        "nodes": [
            {
                "id": "module_main",
                "type": "MODULE",
                "properties": {
                    "module_name": "main",
                    "visibility": "public"
                },
                "parent_id": None,
                "contains": ["func_main"],
                "metric_level": "DEKA_MODULE",
                "dimension": "code_structure"
            },
            {
                "id": "func_main",
                "type": "FUNCTION",
                "properties": {
                    "function_name": "main",
                    "signature": "fn main()",
                    "ownership": {"mode": "owned", "lifetime": None}
                },
                "parent_id": "module_main",
                "contains": ["stmt_println"],
                "metric_level": "BASE_FUNCTION",
                "dimension": "code_structure"
            },
            {
                "id": "stmt_println",
                "type": "STATEMENT",
                "properties": {
                    "statement_type": "macro_call",
                    "code": "println!(\"Hello, world!\");"
                },
                "parent_id": "func_main",
                "contains": [],
                "metric_level": "CENTI_STATEMENT",
                "dimension": "code_structure"
            }
        ],
        "edges": []
    }
```

**Properties:**
- `crate_name` - Crate identifier
- `module_name` - Module identifier
- `struct_name` - Struct identifier
- `function_name` - Function identifier
- `signature` - Full function signature
- `visibility` - public/private
- `ownership` - Ownership mode (owned, borrowed, mutable_borrowed)
- `lifetime` - Lifetime annotation

---

### LLVM Branch

**Node Types:** MODULE, FUNCTION, BASIC_BLOCK, INSTRUCTION, VALUE
**Edge Relations:** CONTAINS, BRANCHES, USES, DEFINES, DOMINATES
**Primary Dimension:** ssa_structure
**Common Extensions:** ssa, control_flow, typed

#### Minimal Template (4 nodes)

```python
def generate_llvm_minimal() -> dict:
    """Generate minimal LLVM TRUG.
    
    Structure:
    - 1 MODULE (root)
    - 1 FUNCTION
    - 1 BASIC_BLOCK
    - 1 INSTRUCTION (ret)
    """
    return {
        "name": "LLVM Minimal Example",
        "version": "1.0.0",
        "type": "CODE",
        "dimensions": {
            "ssa_structure": {
                "description": "LLVM SSA hierarchy",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": ["ssa", "control_flow"],  # LLVM requires SSA
            "vocabularies": ["llvm_18"],
            "profiles": []
        },
        "nodes": [
            {
                "id": "module_main",
                "type": "MODULE",
                "properties": {
                    "module_name": "main.ll",
                    "target_triple": "x86_64-unknown-linux-gnu"
                },
                "parent_id": None,
                "contains": ["func_main"],
                "metric_level": "DEKA_MODULE",
                "dimension": "ssa_structure"
            },
            {
                "id": "func_main",
                "type": "FUNCTION",
                "properties": {
                    "function_name": "main",
                    "signature": "i32 @main()",
                    "ssa_version": 1
                },
                "parent_id": "module_main",
                "contains": ["bb_entry"],
                "metric_level": "BASE_FUNCTION",
                "dimension": "ssa_structure"
            },
            {
                "id": "bb_entry",
                "type": "BASIC_BLOCK",
                "properties": {
                    "label": "entry",
                    "control_flow": {
                        "predecessors": [],
                        "successors": []
                    }
                },
                "parent_id": "func_main",
                "contains": ["inst_ret"],
                "metric_level": "DECI_BLOCK",
                "dimension": "ssa_structure"
            },
            {
                "id": "inst_ret",
                "type": "INSTRUCTION",
                "properties": {
                    "opcode": "ret",
                    "operands": ["i32 0"],
                    "ssa_def": None
                },
                "parent_id": "bb_entry",
                "contains": [],
                "metric_level": "CENTI_INSTRUCTION",
                "dimension": "ssa_structure"
            }
        ],
        "edges": []
    }
```

**Properties:**
- `module_name` - Module/file name
- `target_triple` - Compilation target
- `function_name` - Function identifier
- `signature` - LLVM function signature
- `label` - Basic block label
- `opcode` - LLVM instruction opcode
- `operands` - Instruction operands
- `ssa_def` - SSA register defined (if any)
- `ssa_version` - SSA version number

---

### Web Branch

**Node Types:** SITE, PAGE, SECTION, COMPONENT, ELEMENT
**Edge Relations:** CONTAINS, LINKS_TO, NAVIGATES_TO, EMBEDS
**Primary Dimension:** web_structure
**Common Extensions:** scoped (for CSS), typed (for TypeScript)

#### Minimal Template (3 nodes)

```python
def generate_web_minimal() -> dict:
    """Generate minimal Web TRUG.
    
    Structure:
    - 1 SITE (root)
    - 1 PAGE
    - 1 SECTION
    """
    return {
        "name": "Web Minimal Example",
        "version": "1.0.0",
        "type": "WEB",
        "dimensions": {
            "web_structure": {
                "description": "Website hierarchy",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["html5"],
            "profiles": []
        },
        "nodes": [
            {
                "id": "site_root",
                "type": "SITE",
                "properties": {
                    "site_name": "Example Site",
                    "url": "https://example.com",
                    "description": "Example website"
                },
                "parent_id": None,
                "contains": ["page_home"],
                "metric_level": "DEKA_SITE",
                "dimension": "web_structure"
            },
            {
                "id": "page_home",
                "type": "PAGE",
                "properties": {
                    "page_title": "Home",
                    "url": "/",
                    "meta": {
                        "description": "Home page"
                    }
                },
                "parent_id": "site_root",
                "contains": ["section_hero"],
                "metric_level": "BASE_PAGE",
                "dimension": "web_structure"
            },
            {
                "id": "section_hero",
                "type": "SECTION",
                "properties": {
                    "section_id": "hero",
                    "content": "Welcome to our site"
                },
                "parent_id": "page_home",
                "contains": [],
                "metric_level": "DECI_SECTION",
                "dimension": "web_structure"
            }
        ],
        "edges": []
    }
```

**Properties:**
- `site_name` - Site identifier
- `url` - Full URL or path
- `page_title` - Page title
- `meta` - Meta information (description, keywords)
- `section_id` - Section identifier
- `content` - Text content

---

### Writer Branch

**Node Types:** WORK, CHAPTER, SECTION, PARAGRAPH, SENTENCE
**Edge Relations:** CONTAINS, REFERENCES, CITES, QUOTES
**Primary Dimension:** document_structure
**Common Extensions:** None typically required

#### Minimal Template (3 nodes)

```python
def generate_writer_minimal() -> dict:
    """Generate minimal Writer TRUG.
    
    Structure:
    - 1 WORK (root)
    - 1 CHAPTER
    - 1 PARAGRAPH
    """
    return {
        "name": "Writer Minimal Example",
        "version": "1.0.0",
        "type": "WRITER",
        "dimensions": {
            "document_structure": {
                "description": "Document hierarchy",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["markdown"],
            "profiles": []
        },
        "nodes": [
            {
                "id": "work_essay",
                "type": "WORK",
                "properties": {
                    "title": "Sample Essay",
                    "author": "Example Author",
                    "word_count": 150
                },
                "parent_id": None,
                "contains": ["chapter_intro"],
                "metric_level": "DEKA_WORK",
                "dimension": "document_structure"
            },
            {
                "id": "chapter_intro",
                "type": "CHAPTER",
                "properties": {
                    "chapter_number": 1,
                    "title": "Introduction",
                    "word_count": 50
                },
                "parent_id": "work_essay",
                "contains": ["para_opening"],
                "metric_level": "BASE_CHAPTER",
                "dimension": "document_structure"
            },
            {
                "id": "para_opening",
                "type": "PARAGRAPH",
                "properties": {
                    "content": "This is the opening paragraph of our essay.",
                    "word_count": 8
                },
                "parent_id": "chapter_intro",
                "contains": [],
                "metric_level": "CENTI_PARAGRAPH",
                "dimension": "document_structure"
            }
        ],
        "edges": []
    }
```

**Properties:**
- `title` - Work/chapter/section title
- `author` - Author name
- `chapter_number` - Chapter number
- `word_count` - Word count
- `content` - Text content

---

### Semantic Branch

**Node Types:** CONCEPT, RELATIONSHIP, ENTITY, ATTRIBUTE
**Edge Relations:** CONTAINS, RELATES_TO, IS_A, HAS_A
**Primary Dimension:** semantic_structure
**Common Extensions:** typed (for semantic types)

#### Minimal Template (3 nodes)

```python
def generate_semantic_minimal() -> dict:
    """Generate minimal Semantic TRUG.
    
    Structure:
    - 1 CONCEPT (root)
    - 1 ENTITY
    - 1 ATTRIBUTE
    """
    return {
        "name": "Semantic Minimal Example",
        "version": "1.0.0",
        "type": "SEMANTIC",
        "dimensions": {
            "semantic_structure": {
                "description": "Semantic hierarchy",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["rdfs"],
            "profiles": []
        },
        "nodes": [
            {
                "id": "concept_person",
                "type": "CONCEPT",
                "properties": {
                    "concept_name": "Person",
                    "definition": "A human being"
                },
                "parent_id": None,
                "contains": ["entity_john"],
                "metric_level": "DEKA_CONCEPT",
                "dimension": "semantic_structure"
            },
            {
                "id": "entity_john",
                "type": "ENTITY",
                "properties": {
                    "entity_name": "John",
                    "instance_of": "Person"
                },
                "parent_id": "concept_person",
                "contains": ["attr_age"],
                "metric_level": "BASE_ENTITY",
                "dimension": "semantic_structure"
            },
            {
                "id": "attr_age",
                "type": "ATTRIBUTE",
                "properties": {
                    "attribute_name": "age",
                    "value": 30,
                    "type": "integer"
                },
                "parent_id": "entity_john",
                "contains": [],
                "metric_level": "CENTI_ATTRIBUTE",
                "dimension": "semantic_structure"
            }
        ],
        "edges": []
    }
```

**Properties:**
- `concept_name` - Concept identifier
- `definition` - Concept definition
- `entity_name` - Entity identifier
- `instance_of` - Type/class
- `attribute_name` - Attribute name
- `value` - Attribute value
- `type` - Value type

---

## Extension System

Extensions add additional properties to nodes. The generator can apply extensions to any branch template.

### typed Extension

**Adds:** Type information to nodes

```python
def apply_typed_extension(node: dict) -> dict:
    """Add type information to node.
    
    For FUNCTION nodes:
    - return_type
    - parameter_types
    
    For VARIABLE nodes:
    - variable_type
    """
    if node['type'] == 'FUNCTION':
        node['properties']['return_type'] = 'str'
        node['properties']['parameter_types'] = ['str']
    elif node['type'] == 'STATEMENT' and 'variable' in node['properties']:
        node['properties']['variable_type'] = 'int'
    
    return node
```

---

### ssa Extension

**Adds:** SSA (Static Single Assignment) information

```python
def apply_ssa_extension(node: dict) -> dict:
    """Add SSA information to node.
    
    For INSTRUCTION/STATEMENT nodes:
    - ssa_def: Register/variable defined
    - ssa_uses: Registers/variables used
    - ssa_version: Version number
    """
    if node['type'] in ['INSTRUCTION', 'STATEMENT']:
        node['properties']['ssa_def'] = f"%{node['id']}.0"
        node['properties']['ssa_uses'] = []
        node['properties']['ssa_version'] = 0
    
    return node
```

---

### control_flow Extension

**Adds:** Control flow information

```python
def apply_control_flow_extension(node: dict) -> dict:
    """Add control flow information to node.
    
    For BASIC_BLOCK nodes:
    - predecessors: List of predecessor block IDs
    - successors: List of successor block IDs
    - dominators: List of dominator block IDs
    """
    if node['type'] == 'BASIC_BLOCK':
        node['properties']['control_flow'] = {
            'predecessors': [],
            'successors': [],
            'dominators': []
        }
    
    return node
```

---

### scoped Extension

**Adds:** Scope information

```python
def apply_scoped_extension(node: dict) -> dict:
    """Add scope information to node.
    
    For any node that can have scope:
    - scope_id: Unique scope identifier
    - parent_scope_id: Parent scope (or null)
    - bindings: Variables/names bound in this scope
    """
    if node['type'] in ['MODULE', 'CLASS', 'FUNCTION', 'BLOCK']:
        node['properties']['scope_id'] = f"scope_{node['id']}"
        node['properties']['parent_scope_id'] = None
        node['properties']['bindings'] = []
    
    return node
```

---

### ownership Extension

**Adds:** Rust ownership information

```python
def apply_ownership_extension(node: dict) -> dict:
    """Add Rust ownership information to node.
    
    For VALUE/VARIABLE nodes:
    - ownership_mode: owned, borrowed, mutable_borrowed
    - lifetime: Lifetime annotation (or None)
    - borrow_checker_status: valid, moved, borrowed
    """
    if node['type'] in ['VALUE', 'VARIABLE', 'PARAMETER']:
        node['properties']['ownership'] = {
            'mode': 'owned',
            'lifetime': None,
            'borrow_checker_status': 'valid'
        }
    
    return node
```

---

## API Design

### Python Library API

```python
from trugs_tools import generate_trug

# Generate minimal template
trug = generate_trug(branch="python", template="minimal")

# Generate complete template
trug = generate_trug(branch="python", template="complete")

# Add extensions
trug = generate_trug(
    branch="python",
    template="minimal",
    extensions=["typed", "scoped"]
)

# Save to file
with open("example.json", "w") as f:
    json.dump(trug, f, indent=2)
```

### Generator Function Signature

```python
def generate_trug(
    branch: str,
    template: str = "minimal",
    extensions: list[str] = None,
    validate: bool = True,
    pretty: bool = True
) -> dict:
    """Generate a TRUG example.
    
    Args:
        branch: Branch name (python, rust, llvm, web, writer, semantic)
        template: Template type (minimal, complete)
        extensions: List of extension names (typed, ssa, control_flow, scoped, ownership)
        validate: Validate output before returning (default: True)
        pretty: Pretty-print with indentation (default: True)
    
    Returns:
        Dictionary representing a valid TRUG
    
    Raises:
        ValueError: If branch or template is invalid
        ValidationError: If generated TRUG fails validation
    """
```

---

## CLI Design

### Command Interface

```bash
# Generate minimal Python TRUG
trugs-generate --branch python

# Generate complete Python TRUG
trugs-generate --branch python --template complete

# Add extensions
trugs-generate --branch python --extension typed --extension scoped

# Save to file
trugs-generate --branch python --output example.json

# Generate all branches (minimal)
trugs-generate --all --output-dir examples/

# Generate with custom name
trugs-generate --branch rust --name "My Rust Example"
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--branch BRANCH` | Branch name (required unless --all) | None |
| `--template TYPE` | Template type (minimal, complete) | minimal |
| `--extension EXT` | Add extension (repeatable) | [] |
| `--output FILE` | Output file path | stdout |
| `--output-dir DIR` | Output directory (with --all) | . |
| `--name NAME` | Custom TRUG name | Auto-generated |
| `--all` | Generate all branches | False |
| `--validate` | Validate before output | True |
| `--no-validate` | Skip validation | False |

### Output Examples

**Success:**
```bash
$ trugs-generate --branch python
{
  "name": "Python Minimal Example",
  "version": "1.0.0",
  ...
}
```

**With Validation:**
```bash
$ trugs-generate --branch python --validate
✓ Generated valid TRUG (3 nodes, 0 edges)
{
  "name": "Python Minimal Example",
  ...
}
```

**Save to File:**
```bash
$ trugs-generate --branch python --output example.json
✓ Generated example.json (3 nodes, 0 edges)
```

---

## Testing Strategy

### Unit Tests

Test each branch template:

```python
# tests/test_generator_python.py
def test_python_minimal():
    """Test Python minimal template generates valid TRUG."""
    trug = generate_trug(branch="python", template="minimal")
    assert trug["version"] == "1.0.0"
    assert trug["type"] == "CODE"
    assert len(trug["nodes"]) >= 3
    
    # Validate
    result = validate_trug(trug)
    assert result.valid

def test_python_complete():
    """Test Python complete template generates valid TRUG."""
    trug = generate_trug(branch="python", template="complete")
    assert len(trug["nodes"]) >= 20
    
    result = validate_trug(trug)
    assert result.valid

def test_python_with_typed():
    """Test Python with typed extension."""
    trug = generate_trug(branch="python", extensions=["typed"])
    
    # Check typed properties added
    for node in trug["nodes"]:
        if node["type"] == "FUNCTION":
            assert "return_type" in node["properties"]
```

### Integration Tests

Test complete generation pipeline:

```python
# tests/test_generator_integration.py
def test_all_branches_minimal():
    """Test all branches generate valid minimal TRUGs."""
    branches = ["python", "rust", "llvm", "web", "writer", "semantic"]
    
    for branch in branches:
        trug = generate_trug(branch=branch, template="minimal")
        result = validate_trug(trug)
        assert result.valid, f"{branch} minimal template failed validation"

def test_all_extensions():
    """Test all extensions can be applied."""
    extensions = ["typed", "ssa", "control_flow", "scoped", "ownership"]
    
    for ext in extensions:
        trug = generate_trug(branch="python", extensions=[ext])
        result = validate_trug(trug)
        assert result.valid

def test_cli_generates_file():
    """Test CLI generates file successfully."""
    import subprocess
    import os
    
    result = subprocess.run(
        ["trugs-generate", "--branch", "python", "--output", "/tmp/test.json"],
        capture_output=True
    )
    
    assert result.returncode == 0
    assert os.path.exists("/tmp/test.json")
```

### Test Coverage Goals

- **Unit Tests:** 100% coverage for each template generator
- **Integration Tests:** All branch + extension combinations
- **CLI Tests:** All command-line options
- **Overall:** >90% code coverage

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `generator.py` with main `generate_trug()` function
- [ ] Create `templates/__init__.py`
- [ ] Create `extensions.py` with extension appliers
- [ ] Add validation integration

### Phase 2: Branch Templates (Minimal)
- [ ] Implement `templates/python.py` - minimal template
- [ ] Implement `templates/rust.py` - minimal template
- [ ] Implement `templates/llvm.py` - minimal template
- [ ] Implement `templates/web.py` - minimal template
- [ ] Implement `templates/writer.py` - minimal template
- [ ] Implement `templates/semantic.py` - minimal template

### Phase 3: Branch Templates (Complete)
- [ ] Implement Python complete template (20+ nodes)
- [ ] Implement Rust complete template
- [ ] Implement LLVM complete template
- [ ] Implement Web complete template
- [ ] Implement Writer complete template
- [ ] Implement Semantic complete template

### Phase 4: Extensions
- [ ] Implement `apply_typed_extension()`
- [ ] Implement `apply_ssa_extension()`
- [ ] Implement `apply_control_flow_extension()`
- [ ] Implement `apply_scoped_extension()`
- [ ] Implement `apply_ownership_extension()`

### Phase 5: CLI
- [ ] Create CLI argument parser
- [ ] Implement `--branch` option
- [ ] Implement `--template` option
- [ ] Implement `--extension` option (repeatable)
- [ ] Implement `--output` option
- [ ] Implement `--all` option
- [ ] Add `--help` documentation

### Phase 6: Testing
- [ ] Write unit tests for each branch (minimal + complete)
- [ ] Write unit tests for each extension
- [ ] Write integration tests
- [ ] Write CLI tests
- [ ] Achieve >90% code coverage

### Phase 7: Documentation
- [ ] Write API documentation
- [ ] Write CLI usage guide
- [ ] Create examples directory with all generated TRUGs
- [ ] Add template customization guide

---

## Dependencies

### Required
- Python 3.8+
- Standard library (json, dataclasses)

### Optional
- trugs_tools.validator (for validation)

### Testing
- pytest
- pytest-cov

---

## Future Enhancements

**Not in v1.0, but valuable for future versions:**

1. **Custom Templates** - User-defined templates
2. **Template Inheritance** - Extend existing templates
3. **Randomization** - Generate random valid TRUGs for testing
4. **Import from Source** - Generate TRUG from actual code (Python, Rust, etc.)
5. **Interactive Mode** - Guided template generation
6. **Template Gallery** - Community-contributed templates
7. **Diff Templates** - Show differences between template versions

---

## Specification Status

✅ **Complete** - Ready for implementation

**Next Steps:**
1. Review this specification
2. Implement Phase 1: Core Infrastructure
3. Implement Phase 2: Minimal templates for all branches
4. Test and validate

---

## References

- [TRUGS_PROTOCOL/BRANCHES.md](../TRUGS_PROTOCOL/BRANCHES.md) - Branch specifications
- [TRUGS_PROTOCOL/SPEC_extensions.md](../TRUGS_PROTOCOL/SPEC_extensions.md) - Extension specifications
- [TRUGS_PROTOCOL/SCHEMA.md](../TRUGS_PROTOCOL/SCHEMA.md) - Complete schema reference
- [SPEC_validator.md](SPEC_validator.md) - Validator specification
- [AAA.md](AAA.md) - TRUGS_TOOLS project overview
