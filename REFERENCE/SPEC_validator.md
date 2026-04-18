# TRUGS_TOOLS: Validator Specification

**Version:** 1.0.0 (AAA_AARDVARK)
**Component:** TRUGS_TOOLS Validator
**Status:** ✅ Specification Complete
**Last Updated:** 2026-02-10
**Parent:** [AAA.md](AAA.md)

---

## Purpose

The TRUGS Validator is a Python library and CLI tool that verifies TRUG files conform to the TRUGS v1.0 specification. It implements all 9 Core validation rules defined in [TRUGS_PROTOCOL/SPEC_validation.md](../TRUGS_PROTOCOL/SPEC_validation.md).

**What it validates:**
- ✅ CORE structure (7 node fields, 3 edge fields)
- ✅ Hierarchy consistency (parent_id ↔ contains)
- ✅ Metric level ordering (parent ≥ child)
- ✅ Dimension declarations
- ✅ Required fields presence
- ✅ Graph integrity (no dangling references)

**What it does NOT validate:**
- ❌ Node type vocabularies (branch-specific)
- ❌ Property schemas (properties are open)
- ❌ Domain-specific semantics

---

## Architecture

### Design Principles

1. **Rule Isolation** - Each validation rule is an independent, testable function
2. **Clear Error Messages** - Every failure includes location and fix guidance
3. **Fail-Fast** - Stop on first structural error, continue for semantic errors
4. **Zero Dependencies** - Only Python stdlib (JSON parsing)
5. **Performance** - O(n) validation for n nodes, single-pass when possible

### Module Structure

```
trugs_tools/
├── validator.py          # Main validator API
├── rules.py              # 9 validation rules
└── errors.py             # Error types and formatting
```

### Validation Pipeline

```
Input: TRUG JSON file
  ↓
1. Parse JSON (fail-fast on syntax error)
  ↓
2. Validate Structure (required root fields)
  ↓
3. Validate Nodes (Rule 1: unique IDs)
  ↓
4. Validate Edges (Rule 2: valid references)
  ↓
5. Validate Hierarchy (Rule 3: parent ↔ contains)
  ↓
6. Validate Metrics (Rule 4: level ordering)
  ↓
7. Validate Dimensions (Rule 5: declarations)
  ↓
8. Validate Required Fields (Rule 6, 7, 8)
  ↓
9. Validate Format (Rule 9: metric_level format)
  ↓
Output: ValidationResult
```

---

## The 9 Validation Rules

### Rule 1: Node ID Uniqueness

**Error Code:** `DUPLICATE_NODE_ID`

**Check:** All node IDs must be unique within the graph

**Implementation:**
```python
def validate_unique_ids(nodes: list) -> list[ValidationError]:
    """Check that all node IDs are unique.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    seen_ids = set()
    
    for i, node in enumerate(nodes):
        node_id = node.get('id')
        if not node_id:
            errors.append(ValidationError(
                code='MISSING_NODE_ID',
                message=f"Node at index {i} missing 'id' field",
                location=f"nodes[{i}]"
            ))
        elif node_id in seen_ids:
            errors.append(ValidationError(
                code='DUPLICATE_NODE_ID',
                message=f"Duplicate node ID: '{node_id}'",
                location=f"nodes[{i}].id",
                hint="Each node must have a unique ID"
            ))
        else:
            seen_ids.add(node_id)
    
    return errors
```

---

### Rule 2: Edge Reference Validity

**Error Code:** `INVALID_EDGE_REFERENCE`

**Check:** Edge `from_id` and `to_id` must reference existing nodes

**Implementation:**
```python
def validate_edge_references(nodes: list, edges: list) -> list[ValidationError]:
    """Check that all edges reference existing nodes.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    node_ids = {node['id'] for node in nodes if 'id' in node}
    
    for i, edge in enumerate(edges):
        from_id = edge.get('from_id')
        to_id = edge.get('to_id')
        
        if not from_id:
            errors.append(ValidationError(
                code='MISSING_FROM_ID',
                message=f"Edge at index {i} missing 'from_id' field",
                location=f"edges[{i}]"
            ))
        elif from_id not in node_ids:
            errors.append(ValidationError(
                code='INVALID_EDGE_REFERENCE',
                message=f"Edge from_id '{from_id}' references non-existent node",
                location=f"edges[{i}].from_id",
                hint=f"Add node with id='{from_id}' or fix edge reference"
            ))
        
        if not to_id:
            errors.append(ValidationError(
                code='MISSING_TO_ID',
                message=f"Edge at index {i} missing 'to_id' field",
                location=f"edges[{i}]"
            ))
        elif to_id not in node_ids:
            errors.append(ValidationError(
                code='INVALID_EDGE_REFERENCE',
                message=f"Edge to_id '{to_id}' references non-existent node",
                location=f"edges[{i}].to_id",
                hint=f"Add node with id='{to_id}' or fix edge reference"
            ))
    
    return errors
```

---

### Rule 3: Hierarchy Consistency

**Error Code:** `INCONSISTENT_HIERARCHY`

**Check:** Parent's `contains` must match children's `parent_id` (bidirectional)

**Implementation:**
```python
def validate_hierarchy_consistency(nodes: list) -> list[ValidationError]:
    """Check bidirectional parent-child consistency.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    nodes_by_id = {n['id']: n for n in nodes if 'id' in n}
    
    for node in nodes:
        node_id = node.get('id')
        if not node_id:
            continue  # Caught by Rule 1
        
        parent_id = node.get('parent_id')
        contains = node.get('contains', [])
        
        # Check: If node has parent, parent must list it in contains[]
        if parent_id is not None:
            if parent_id not in nodes_by_id:
                errors.append(ValidationError(
                    code='INVALID_PARENT_REFERENCE',
                    message=f"Node '{node_id}' parent_id '{parent_id}' references non-existent node",
                    location=f"nodes[{node_id}].parent_id"
                ))
            else:
                parent = nodes_by_id[parent_id]
                parent_contains = parent.get('contains', [])
                if node_id not in parent_contains:
                    errors.append(ValidationError(
                        code='INCONSISTENT_HIERARCHY',
                        message=f"Node '{node_id}' claims parent '{parent_id}', but parent doesn't list it in contains[]",
                        location=f"nodes[{node_id}].parent_id",
                        hint=f"Add '{node_id}' to nodes[{parent_id}].contains[] array"
                    ))
        
        # Check: Every child in contains[] must have this node as parent
        for child_id in contains:
            if child_id not in nodes_by_id:
                errors.append(ValidationError(
                    code='INVALID_CHILD_REFERENCE',
                    message=f"Node '{node_id}' contains[] references non-existent node '{child_id}'",
                    location=f"nodes[{node_id}].contains"
                ))
            else:
                child = nodes_by_id[child_id]
                child_parent_id = child.get('parent_id')
                if child_parent_id != node_id:
                    errors.append(ValidationError(
                        code='INCONSISTENT_HIERARCHY',
                        message=f"Node '{node_id}' lists '{child_id}' in contains[], but child has parent_id='{child_parent_id}'",
                        location=f"nodes[{node_id}].contains",
                        hint=f"Set nodes[{child_id}].parent_id to '{node_id}'"
                    ))
    
    return errors
```

---

### Rule 4: Metric Level Ordering

**Error Code:** `INVALID_METRIC_ORDERING`

**Check:** Parent metric level ≥ child metric level (within same dimension)

**Implementation:**
```python
METRIC_VALUES = {
    "YOTTA": 1e24, "ZETTA": 1e21, "EXA": 1e18, "PETA": 1e15,
    "TERA": 1e12, "GIGA": 1e9, "MEGA": 1e6, "KILO": 1e3,
    "HECTO": 1e2, "DEKA": 1e1, "BASE": 1e0, "DECI": 1e-1,
    "CENTI": 1e-2, "MILLI": 1e-3, "MICRO": 1e-6, "NANO": 1e-9,
    "PICO": 1e-12, "FEMTO": 1e-15, "ATTO": 1e-18,
    "ZEPTO": 1e-21, "YOCTO": 1e-24
}

def parse_metric_level(level_name: str) -> tuple[str, float]:
    """Parse metric level to prefix and numeric value.
    
    Args:
        level_name: Format {PREFIX}_{SEMANTIC} (e.g., "BASE_FUNCTION")
    
    Returns:
        Tuple of (prefix, numeric_value)
    
    Raises:
        ValueError: If format is invalid
    """
    parts = level_name.split('_', 1)
    if len(parts) < 2:
        raise ValueError(f"Invalid format: '{level_name}' (expected PREFIX_NAME)")
    
    prefix = parts[0]
    if prefix not in METRIC_VALUES:
        raise ValueError(f"Invalid metric prefix: '{prefix}'")
    
    return prefix, METRIC_VALUES[prefix]

def validate_metric_ordering(nodes: list) -> list[ValidationError]:
    """Check parent metric ≥ child metric within same dimension.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    nodes_by_id = {n['id']: n for n in nodes if 'id' in n}
    
    for node in nodes:
        node_id = node.get('id')
        parent_id = node.get('parent_id')
        
        if parent_id and parent_id in nodes_by_id:
            parent = nodes_by_id[parent_id]
            
            # Only check if same dimension
            if parent.get('dimension') == node.get('dimension'):
                try:
                    parent_prefix, parent_val = parse_metric_level(parent['metric_level'])
                    child_prefix, child_val = parse_metric_level(node['metric_level'])
                    
                    if parent_val < child_val:
                        errors.append(ValidationError(
                            code='INVALID_METRIC_ORDERING',
                            message=(
                                f"Node '{node_id}' metric_level ({node['metric_level']} = {child_val}) "
                                f"exceeds parent metric_level ({parent['metric_level']} = {parent_val})"
                            ),
                            location=f"nodes[{node_id}].metric_level",
                            hint="Parent metric level must be ≥ child metric level"
                        ))
                except ValueError as e:
                    # Invalid format - will be caught by Rule 9
                    pass
    
    return errors
```

---

### Rule 5: Dimension Declaration

**Error Code:** `UNDECLARED_DIMENSION`

**Check:** All node dimensions must be declared in root `dimensions` object

**Implementation:**
```python
def validate_dimension_declarations(graph: dict) -> list[ValidationError]:
    """Check all node dimensions are declared.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    declared_dims = set(graph.get('dimensions', {}).keys())
    
    for node in graph.get('nodes', []):
        node_id = node.get('id')
        dimension = node.get('dimension')
        
        if dimension and dimension not in declared_dims:
            errors.append(ValidationError(
                code='UNDECLARED_DIMENSION',
                message=f"Node '{node_id}' uses undeclared dimension '{dimension}'",
                location=f"nodes[{node_id}].dimension",
                hint=f"Add '{dimension}' to root dimensions object"
            ))
    
    return errors
```

---

### Rule 6: Required Node Fields

**Error Code:** `MISSING_REQUIRED_FIELD`

**Check:** All 7 required node fields must be present

**Implementation:**
```python
REQUIRED_NODE_FIELDS = ['id', 'type', 'properties', 'parent_id', 'contains', 'metric_level', 'dimension']

def validate_required_node_fields(nodes: list) -> list[ValidationError]:
    """Check all nodes have required fields.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    
    for i, node in enumerate(nodes):
        node_id = node.get('id', f'<node at index {i}>')
        
        for field in REQUIRED_NODE_FIELDS:
            if field not in node:
                errors.append(ValidationError(
                    code='MISSING_REQUIRED_FIELD',
                    message=f"Node '{node_id}' missing required field '{field}'",
                    location=f"nodes[{node_id}]",
                    hint=f"Add '{field}' field to node"
                ))
            elif field == 'properties' and node[field] is None:
                errors.append(ValidationError(
                    code='NULL_PROPERTIES',
                    message=f"Node '{node_id}' has null properties (use empty object {{}} instead)",
                    location=f"nodes[{node_id}].properties",
                    hint="Change 'properties': null to 'properties': {}"
                ))
            elif field == 'contains' and node[field] is None:
                errors.append(ValidationError(
                    code='NULL_CONTAINS',
                    message=f"Node '{node_id}' has null contains (use empty array [] instead)",
                    location=f"nodes[{node_id}].contains",
                    hint="Change 'contains': null to 'contains': []"
                ))
    
    return errors
```

---

### Rule 7: Required Edge Fields

**Error Code:** `MISSING_REQUIRED_FIELD`

**Check:** All 3 required edge fields must be present

**Implementation:**
```python
REQUIRED_EDGE_FIELDS = ['from_id', 'to_id', 'relation']

def validate_required_edge_fields(edges: list) -> list[ValidationError]:
    """Check all edges have required fields.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    
    for i, edge in enumerate(edges):
        for field in REQUIRED_EDGE_FIELDS:
            if field not in edge:
                errors.append(ValidationError(
                    code='MISSING_REQUIRED_FIELD',
                    message=f"Edge at index {i} missing required field '{field}'",
                    location=f"edges[{i}]",
                    hint=f"Add '{field}' field to edge"
                ))
    
    return errors
```

---

### Rule 8: Required Graph Fields

**Error Code:** `MISSING_REQUIRED_FIELD`

**Check:** Graph root must have required fields

**Implementation:**
```python
REQUIRED_GRAPH_FIELDS = ['name', 'version', 'type', 'dimensions', 'capabilities', 'nodes', 'edges']

def validate_required_graph_fields(graph: dict) -> list[ValidationError]:
    """Check graph has required root fields.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    
    for field in REQUIRED_GRAPH_FIELDS:
        if field not in graph:
            errors.append(ValidationError(
                code='MISSING_REQUIRED_FIELD',
                message=f"Graph missing required field '{field}'",
                location="root",
                hint=f"Add '{field}' field to root object"
            ))
    
    # Check version is 1.0.0
    version = graph.get('version')
    if version != '1.0.0':
        errors.append(ValidationError(
            code='INVALID_VERSION',
            message=f"Graph version '{version}' is not supported (expected '1.0.0')",
            location="root.version",
            hint="Set version to '1.0.0'"
        ))
    
    # Check capabilities structure
    capabilities = graph.get('capabilities', {})
    if not isinstance(capabilities, dict):
        errors.append(ValidationError(
            code='INVALID_CAPABILITIES',
            message="capabilities must be an object",
            location="root.capabilities"
        ))
    else:
        for field in ['extensions', 'vocabularies', 'profiles']:
            if field not in capabilities:
                errors.append(ValidationError(
                    code='MISSING_REQUIRED_FIELD',
                    message=f"capabilities missing required field '{field}'",
                    location="root.capabilities",
                    hint=f"Add '{field}': [] to capabilities"
                ))
    
    return errors
```

---

### Rule 9: Metric Level Format

**Error Code:** `INVALID_METRIC_FORMAT`

**Check:** metric_level must follow `{PREFIX}_{NAME}` format with valid SI prefix

**Implementation:**
```python
def validate_metric_format(nodes: list) -> list[ValidationError]:
    """Check metric_level format is valid.
    
    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors = []
    
    for node in nodes:
        node_id = node.get('id')
        metric_level = node.get('metric_level')
        
        if not metric_level:
            continue  # Caught by Rule 6
        
        try:
            parse_metric_level(metric_level)
        except ValueError as e:
            errors.append(ValidationError(
                code='INVALID_METRIC_FORMAT',
                message=f"Node '{node_id}' has invalid metric_level: {str(e)}",
                location=f"nodes[{node_id}].metric_level",
                hint="Format must be PREFIX_NAME (e.g., BASE_FUNCTION, CENTI_STATEMENT)"
            ))
    
    return errors
```

---

## API Design

### Python Library API

```python
from trugs_tools import validate_trug, ValidationResult, ValidationError

# Validate from file
result = validate_trug("example.json")

# Validate from dict
data = {"name": "test", "version": "1.0.0", ...}
result = validate_trug(data)

# Check result
if result.valid:
    print("✓ Valid TRUG")
else:
    print(f"✗ {len(result.errors)} errors found:")
    for error in result.errors:
        print(f"  [{error.code}] {error.location}: {error.message}")
        if error.hint:
            print(f"    Hint: {error.hint}")
```

### ValidationResult Class

```python
@dataclass
class ValidationResult:
    """Result of TRUG validation."""
    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    graph: dict | None  # Parsed graph if validation passed
    
    def summary(self) -> str:
        """Human-readable summary."""
        if self.valid:
            return "✓ Valid TRUG"
        else:
            return f"✗ {len(self.errors)} errors, {len(self.warnings)} warnings"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings]
        }
```

### ValidationError Class

```python
@dataclass
class ValidationError:
    """Single validation error."""
    code: str           # Error code (e.g., DUPLICATE_NODE_ID)
    message: str        # Human-readable message
    location: str       # Where in graph (e.g., nodes[func_1].parent_id)
    hint: str = ""      # Optional fix suggestion
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "location": self.location,
            "hint": self.hint
        }
```

---

## CLI Design

### Command Interface

```bash
# Validate single file
tg validate <file.json>

# Validate multiple files
tg validate file1.json file2.json file3.json

# Validate from stdin
cat example.json | tg validate -

# Output formats
tg validate --format json file.json
tg validate --format text file.json (default)

# Verbosity levels
tg validate --quiet file.json      # Only show summary
tg validate --verbose file.json    # Show all details
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All files valid |
| 1 | Validation errors found |
| 2 | File not found or read error |
| 3 | Invalid JSON syntax |
| 4 | Invalid command-line arguments |

### Output Examples

**Success:**
```
✓ example.json: Valid TRUG (6 nodes, 5 edges)
```

**With Errors:**
```
✗ example.json: 3 errors found

[DUPLICATE_NODE_ID] nodes[1].id
  Duplicate node ID: 'func_main'
  Hint: Each node must have a unique ID

[INCONSISTENT_HIERARCHY] nodes[func_2].parent_id
  Node 'func_2' claims parent 'module_1', but parent doesn't list it in contains[]
  Hint: Add 'func_2' to nodes[module_1].contains[] array

[INVALID_METRIC_ORDERING] nodes[stmt_1].metric_level
  Node 'stmt_1' metric_level (BASE_STATEMENT = 1.0) exceeds parent metric_level (CENTI_FUNCTION = 0.01)
  Hint: Parent metric level must be ≥ child metric level
```

**JSON Output:**
```json
{
  "file": "example.json",
  "valid": false,
  "errors": [
    {
      "code": "DUPLICATE_NODE_ID",
      "message": "Duplicate node ID: 'func_main'",
      "location": "nodes[1].id",
      "hint": "Each node must have a unique ID"
    }
  ],
  "warnings": [],
  "stats": {
    "nodes": 6,
    "edges": 5
  }
}
```

---

## Testing Strategy

### Unit Tests

Each validation rule gets dedicated test suite:

```python
# tests/test_rule_1_unique_ids.py
def test_valid_unique_ids():
    """Test that unique IDs pass validation."""
    nodes = [
        {"id": "node_1", ...},
        {"id": "node_2", ...},
        {"id": "node_3", ...}
    ]
    errors = validate_unique_ids(nodes)
    assert len(errors) == 0

def test_duplicate_id():
    """Test that duplicate IDs are caught."""
    nodes = [
        {"id": "node_1", ...},
        {"id": "node_1", ...}  # Duplicate
    ]
    errors = validate_unique_ids(nodes)
    assert len(errors) == 1
    assert errors[0].code == 'DUPLICATE_NODE_ID'

def test_missing_id():
    """Test that missing IDs are caught."""
    nodes = [
        {"type": "FUNCTION", ...}  # Missing 'id'
    ]
    errors = validate_unique_ids(nodes)
    assert len(errors) == 1
    assert errors[0].code == 'MISSING_NODE_ID'
```

### Integration Tests

Test complete validation pipeline:

```python
# tests/test_integration.py
def test_valid_minimal_trug():
    """Test that minimal valid TRUG passes all rules."""
    trug = load_fixture("minimal_valid.json")
    result = validate_trug(trug)
    assert result.valid
    assert len(result.errors) == 0

def test_complex_hierarchy():
    """Test validation of complex multi-level hierarchy."""
    trug = load_fixture("complex_hierarchy.json")
    result = validate_trug(trug)
    assert result.valid

def test_all_errors():
    """Test that file with multiple errors reports all of them."""
    trug = load_fixture("invalid_multiple_errors.json")
    result = validate_trug(trug)
    assert not result.valid
    assert len(result.errors) >= 3
```

### Fixtures

Create test TRUGs for each scenario:

```
tests/fixtures/
├── minimal_valid.json           # Simplest valid TRUG
├── complex_hierarchy.json       # Multi-level hierarchy
├── multi_dimensional.json       # Multiple dimensions
├── invalid_duplicate_id.json    # Rule 1 violation
├── invalid_edge_ref.json        # Rule 2 violation
├── invalid_hierarchy.json       # Rule 3 violation
├── invalid_metric_order.json    # Rule 4 violation
├── invalid_dimension.json       # Rule 5 violation
├── invalid_missing_fields.json  # Rule 6/7/8 violations
└── invalid_metric_format.json   # Rule 9 violation
```

### Test Coverage Goals

- **Unit Tests:** 100% coverage for each rule function
- **Integration Tests:** Cover all rule combinations
- **CLI Tests:** Test all command-line options and exit codes
- **Overall:** >90% code coverage

---

## Performance Requirements

### Validation Speed

- **Small TRUGs (<100 nodes):** <10ms
- **Medium TRUGs (100-1000 nodes):** <100ms
- **Large TRUGs (1000-10000 nodes):** <1 second
- **Very Large TRUGs (>10000 nodes):** Linear scaling O(n)

### Memory Usage

- **Peak Memory:** <2x TRUG file size
- **Streaming:** Not required for v1.0 (load full graph into memory)

### Optimization Strategies

1. **Single-Pass When Possible** - Combine rule checks that iterate nodes
2. **Early Exit** - Stop on structural errors (invalid JSON, missing required fields)
3. **Index Building** - Build `nodes_by_id` dict once, reuse for all rules
4. **Lazy Validation** - Only validate rules requested by user (optional for v1.0)

---

## Error Message Guidelines

### Good Error Messages

✅ **Specific:** Include exact location and value
✅ **Actionable:** Suggest how to fix
✅ **Contextual:** Explain why it's an error

**Example:**
```
[INCONSISTENT_HIERARCHY] nodes[func_2].parent_id
  Node 'func_2' claims parent 'module_1', but parent doesn't list it in contains[]
  Hint: Add 'func_2' to nodes[module_1].contains[] array
```

### Bad Error Messages

❌ **Vague:** "Invalid hierarchy"
❌ **Cryptic:** "Error at line 42"
❌ **Unhelpful:** "Validation failed"

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `errors.py` with ValidationError and ValidationResult classes
- [ ] Create `rules.py` with METRIC_VALUES constant
- [ ] Implement `parse_metric_level()` helper function
- [ ] Create `validator.py` with `validate_trug()` main function
- [ ] Add JSON parsing and error handling

### Phase 2: Validation Rules
- [ ] Implement Rule 1: validate_unique_ids()
- [ ] Implement Rule 2: validate_edge_references()
- [ ] Implement Rule 3: validate_hierarchy_consistency()
- [ ] Implement Rule 4: validate_metric_ordering()
- [ ] Implement Rule 5: validate_dimension_declarations()
- [ ] Implement Rule 6: validate_required_node_fields()
- [ ] Implement Rule 7: validate_required_edge_fields()
- [ ] Implement Rule 8: validate_required_graph_fields()
- [ ] Implement Rule 9: validate_metric_format()

### Phase 3: CLI
- [ ] Create CLI argument parser
- [ ] Implement file loading and validation loop
- [ ] Add text output formatter
- [ ] Add JSON output formatter
- [ ] Implement exit codes
- [ ] Add --help documentation

### Phase 4: Testing
- [ ] Write unit tests for each rule (100% coverage)
- [ ] Create test fixtures for all scenarios
- [ ] Write integration tests
- [ ] Write CLI tests
- [ ] Add performance benchmarks

### Phase 5: Documentation
- [ ] Write API documentation
- [ ] Write CLI usage guide
- [ ] Create examples directory with valid/invalid TRUGs
- [ ] Add troubleshooting guide

---

## Dependencies

### Required
- Python 3.8+
- Standard library only (json, sys, dataclasses)

### Optional (for CLI)
- argparse (stdlib)
- pathlib (stdlib)

### Testing
- pytest
- pytest-cov (for coverage)

---

## Future Enhancements

**Not in v1.0, but valuable for future versions:**

1. **Streaming Validation** - Validate JSONL files without loading full graph
2. **Partial Validation** - Validate specific rules only
3. **Warning System** - Non-fatal issues (unused nodes, missing descriptions)
4. **Auto-Fix** - Automatically repair common errors
5. **Branch Validation** - Validate node types and properties for specific branches
6. **Schema Validation** - Use JSON Schema for stricter validation
7. **Language Server** - Real-time validation in editors (VS Code, etc.)
8. **Web UI** - Browser-based validation with visual feedback

---

## Specification Status

✅ **Complete** - Ready for implementation

**Next Steps:**
1. Review this specification
2. Create implementation plan
3. Begin Phase 1: Core Infrastructure
4. Implement incrementally with tests

---

## References

- [TRUGS_PROTOCOL/SPEC_validation.md](../TRUGS_PROTOCOL/SPEC_validation.md) - Complete validation rules
- [TRUGS_PROTOCOL/TRUGS_CORE.md](../TRUGS_PROTOCOL/TRUGS_CORE.md) - CORE structure specification
- [TRUGS_PROTOCOL/SCHEMA.md](../TRUGS_PROTOCOL/SCHEMA.md) - Complete schema reference
- [AAA.md](AAA.md) - TRUGS_TOOLS project overview
