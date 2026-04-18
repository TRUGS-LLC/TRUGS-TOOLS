# TRUGS_TOOLS: Analyzer Specification

**Version:** 1.0.0 (AAA_AARDVARK)
**Component:** TRUGS_TOOLS Analyzer
**Status:** ✅ Specification Complete
**Last Updated:** 2026-02-10
**Parent:** [AAA.md](AAA.md)

---

## Purpose

The TRUGS Analyzer is a Python library and CLI tool that extracts information, statistics, and insights from TRUG files. It provides metadata analysis, graph statistics, and structural summaries without modifying the TRUG.

**What it analyzes:**
- ✅ TRUG metadata (name, version, type, extensions)
- ✅ Graph statistics (node count, edge count, depth)
- ✅ Dimension analysis (dimensions used, metric level distribution)
- ✅ Branch and extension information
- ✅ Hierarchy structure (tree depth, branching factor)
- ✅ Node type distribution
- ✅ Edge relation distribution

**Primary Use Cases:**
1. **Quick Overview** - Understand TRUG structure at a glance
2. **Documentation** - Generate statistics for TRUG documentation
3. **Debugging** - Identify structural issues or imbalances
4. **Comparison** - Compare multiple TRUGs
5. **Metrics** - Track TRUG complexity over time

---

## Architecture

### Design Principles

1. **Read-Only** - Never modifies input TRUG
2. **Fast** - Single-pass analysis when possible
3. **Comprehensive** - Extract all useful metadata
4. **Flexible Output** - Text, JSON, or custom formats
5. **No External Dependencies** - Only Python stdlib

### Module Structure

```
trugs_tools/
├── analyzer.py           # Main analyzer API
├── stats.py              # Statistical functions
└── formatters.py         # Output formatters (text, JSON)
```

### Analysis Pipeline

```
Input: TRUG file or dict
  ↓
1. Parse TRUG (if file)
  ↓
2. Extract Metadata (name, version, type, extensions)
  ↓
3. Compute Graph Stats (nodes, edges, dimensions)
  ↓
4. Analyze Hierarchy (depth, branching factor)
  ↓
5. Compute Distributions (node types, edge relations)
  ↓
6. Format Output (text or JSON)
  ↓
Output: AnalysisResult
```

---

## Analysis Categories

### 1. Metadata Analysis

**Extracts:**
- TRUG name
- TRUG version
- TRUG type (CODE, WEB, WRITER, SEMANTIC)
- Extensions used
- Vocabularies used
- Profiles used
- Description (if present)
- Maintainer (if present)
- Last updated (if present)

**Example Output:**
```
Name: Python Fibonacci Example
Version: 1.0.0
Type: CODE
Extensions: typed, scoped
Vocabularies: python_3.12
Profiles: none
```

---

### 2. Graph Statistics

**Computes:**
- Total node count
- Total edge count
- Root node count (nodes with `parent_id` = null)
- Leaf node count (nodes with empty `contains`)
- Average node degree (edges per node)
- Graph density (actual edges / possible edges)

**Example Output:**
```
Nodes: 42
Edges: 38
Roots: 1
Leaves: 20
Avg Degree: 1.81
Density: 0.022
```

---

### 3. Dimension Analysis

**Computes:**
- Dimensions declared
- Nodes per dimension
- Metric level distribution
- Depth per dimension

**Example Output:**
```
Dimensions: code_structure
  Nodes: 42
  Levels: BASE (15), DECI (10), CENTI (17)
  Max Depth: 4
```

---

### 4. Hierarchy Analysis

**Computes:**
- Tree depth (maximum distance from root to leaf)
- Average depth (mean distance to leaves)
- Branching factor (average children per non-leaf node)
- Maximum children (max `contains` array size)

**Example Output:**
```
Hierarchy:
  Max Depth: 4
  Avg Depth: 2.3
  Branching Factor: 2.1
  Max Children: 5
```

---

### 5. Node Type Distribution

**Computes:**
- Count of each node type
- Percentage distribution
- Most common types

**Example Output:**
```
Node Types:
  FUNCTION: 15 (36%)
  STATEMENT: 20 (48%)
  MODULE: 5 (12%)
  CLASS: 2 (4%)
```

---

### 6. Edge Relation Distribution

**Computes:**
- Count of each edge relation
- Percentage distribution
- Most common relations

**Example Output:**
```
Edge Relations:
  CONTAINS: 20 (53%)
  CALLS: 15 (39%)
  IMPORTS: 3 (8%)
```

---

## Implementation

### AnalysisResult Class

```python
@dataclass
class AnalysisResult:
    """Complete analysis of a TRUG."""
    
    # Metadata
    name: str
    version: str
    type: str
    extensions: list[str]
    vocabularies: list[str]
    profiles: list[str]
    description: str | None = None
    maintainer: str | None = None
    updated: str | None = None
    
    # Graph statistics
    node_count: int = 0
    edge_count: int = 0
    root_count: int = 0
    leaf_count: int = 0
    avg_degree: float = 0.0
    density: float = 0.0
    
    # Dimensions
    dimensions: dict[str, DimensionStats] = None
    
    # Hierarchy
    max_depth: int = 0
    avg_depth: float = 0.0
    branching_factor: float = 0.0
    max_children: int = 0
    
    # Distributions
    node_type_dist: dict[str, int] = None
    edge_relation_dist: dict[str, int] = None
    metric_level_dist: dict[str, int] = None
    
    def summary(self) -> str:
        """Human-readable summary."""
        return f"{self.name} ({self.type}, {self.node_count} nodes, {self.edge_count} edges)"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "metadata": {
                "name": self.name,
                "version": self.version,
                "type": self.type,
                "extensions": self.extensions,
                "vocabularies": self.vocabularies,
                "profiles": self.profiles,
                "description": self.description,
                "maintainer": self.maintainer,
                "updated": self.updated
            },
            "statistics": {
                "nodes": self.node_count,
                "edges": self.edge_count,
                "roots": self.root_count,
                "leaves": self.leaf_count,
                "avg_degree": self.avg_degree,
                "density": self.density
            },
            "dimensions": {
                name: dim.to_dict()
                for name, dim in (self.dimensions or {}).items()
            },
            "hierarchy": {
                "max_depth": self.max_depth,
                "avg_depth": self.avg_depth,
                "branching_factor": self.branching_factor,
                "max_children": self.max_children
            },
            "distributions": {
                "node_types": self.node_type_dist or {},
                "edge_relations": self.edge_relation_dist or {},
                "metric_levels": self.metric_level_dist or {}
            }
        }
```

### DimensionStats Class

```python
@dataclass
class DimensionStats:
    """Statistics for a single dimension."""
    name: str
    description: str
    node_count: int
    max_depth: int
    metric_levels: dict[str, int]  # prefix -> count
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "nodes": self.node_count,
            "max_depth": self.max_depth,
            "metric_levels": self.metric_levels
        }
```

### Main Analysis Function

```python
def analyze_trug(trug: dict | str) -> AnalysisResult:
    """Analyze a TRUG file or dictionary.
    
    Args:
        trug: TRUG dictionary or file path
    
    Returns:
        AnalysisResult object
    
    Raises:
        ValueError: If TRUG is invalid
        FileNotFoundError: If file doesn't exist
    """
    # Load if file path
    if isinstance(trug, str):
        with open(trug) as f:
            trug = json.load(f)
    
    # Extract metadata
    metadata = extract_metadata(trug)
    
    # Compute graph statistics
    graph_stats = compute_graph_stats(trug)
    
    # Analyze dimensions
    dim_stats = analyze_dimensions(trug)
    
    # Analyze hierarchy
    hierarchy_stats = analyze_hierarchy(trug)
    
    # Compute distributions
    distributions = compute_distributions(trug)
    
    # Build result
    return AnalysisResult(
        **metadata,
        **graph_stats,
        dimensions=dim_stats,
        **hierarchy_stats,
        **distributions
    )
```

### Helper Functions

```python
def extract_metadata(trug: dict) -> dict:
    """Extract metadata from TRUG."""
    capabilities = trug.get('capabilities', {})
    
    return {
        'name': trug.get('name', 'Unnamed'),
        'version': trug.get('version', 'Unknown'),
        'type': trug.get('type', 'Unknown'),
        'extensions': capabilities.get('extensions', []),
        'vocabularies': capabilities.get('vocabularies', []),
        'profiles': capabilities.get('profiles', []),
        'description': trug.get('description'),
        'maintainer': trug.get('maintainer'),
        'updated': trug.get('updated')
    }

def compute_graph_stats(trug: dict) -> dict:
    """Compute basic graph statistics."""
    nodes = trug.get('nodes', [])
    edges = trug.get('edges', [])
    
    node_count = len(nodes)
    edge_count = len(edges)
    
    root_count = sum(1 for n in nodes if n.get('parent_id') is None)
    leaf_count = sum(1 for n in nodes if len(n.get('contains', [])) == 0)
    
    # Average degree: (edges * 2) / nodes (undirected)
    avg_degree = (edge_count * 2) / node_count if node_count > 0 else 0.0
    
    # Density: actual edges / possible edges
    max_edges = node_count * (node_count - 1) / 2
    density = edge_count / max_edges if max_edges > 0 else 0.0
    
    return {
        'node_count': node_count,
        'edge_count': edge_count,
        'root_count': root_count,
        'leaf_count': leaf_count,
        'avg_degree': avg_degree,
        'density': density
    }

def analyze_dimensions(trug: dict) -> dict[str, DimensionStats]:
    """Analyze each dimension."""
    dimensions = trug.get('dimensions', {})
    nodes = trug.get('nodes', [])
    
    dim_stats = {}
    for dim_name, dim_info in dimensions.items():
        # Nodes in this dimension
        dim_nodes = [n for n in nodes if n.get('dimension') == dim_name]
        
        # Metric level distribution
        metric_levels = {}
        for node in dim_nodes:
            level = node.get('metric_level', '').split('_')[0]
            metric_levels[level] = metric_levels.get(level, 0) + 1
        
        # Max depth in this dimension
        max_depth = compute_max_depth_in_dimension(dim_nodes)
        
        dim_stats[dim_name] = DimensionStats(
            name=dim_name,
            description=dim_info.get('description', ''),
            node_count=len(dim_nodes),
            max_depth=max_depth,
            metric_levels=metric_levels
        )
    
    return dim_stats

def analyze_hierarchy(trug: dict) -> dict:
    """Analyze hierarchy structure."""
    nodes = trug.get('nodes', [])
    nodes_by_id = {n['id']: n for n in nodes}
    
    # Compute depths
    depths = []
    for node in nodes:
        depth = compute_node_depth(node, nodes_by_id)
        depths.append(depth)
    
    max_depth = max(depths) if depths else 0
    avg_depth = sum(depths) / len(depths) if depths else 0.0
    
    # Branching factor
    non_leaf_nodes = [n for n in nodes if len(n.get('contains', [])) > 0]
    if non_leaf_nodes:
        total_children = sum(len(n.get('contains', [])) for n in non_leaf_nodes)
        branching_factor = total_children / len(non_leaf_nodes)
    else:
        branching_factor = 0.0
    
    # Max children
    max_children = max(len(n.get('contains', [])) for n in nodes) if nodes else 0
    
    return {
        'max_depth': max_depth,
        'avg_depth': avg_depth,
        'branching_factor': branching_factor,
        'max_children': max_children
    }

def compute_distributions(trug: dict) -> dict:
    """Compute type and relation distributions."""
    nodes = trug.get('nodes', [])
    edges = trug.get('edges', [])
    
    # Node type distribution
    node_types = {}
    for node in nodes:
        node_type = node.get('type', 'Unknown')
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    # Edge relation distribution
    edge_relations = {}
    for edge in edges:
        relation = edge.get('relation', 'Unknown')
        edge_relations[relation] = edge_relations.get(relation, 0) + 1
    
    # Metric level distribution
    metric_levels = {}
    for node in nodes:
        level = node.get('metric_level', '').split('_')[0]
        metric_levels[level] = metric_levels.get(level, 0) + 1
    
    return {
        'node_type_dist': node_types,
        'edge_relation_dist': edge_relations,
        'metric_level_dist': metric_levels
    }

def compute_node_depth(node: dict, nodes_by_id: dict) -> int:
    """Compute depth of node from root."""
    depth = 0
    current = node
    
    while current.get('parent_id') is not None:
        parent_id = current['parent_id']
        if parent_id not in nodes_by_id:
            break  # Broken hierarchy
        current = nodes_by_id[parent_id]
        depth += 1
    
    return depth

def compute_max_depth_in_dimension(nodes: list) -> int:
    """Compute maximum depth in dimension."""
    if not nodes:
        return 0
    
    nodes_by_id = {n['id']: n for n in nodes}
    depths = [compute_node_depth(n, nodes_by_id) for n in nodes]
    return max(depths) if depths else 0
```

---

## Output Formatters

### Text Formatter

```python
def format_text(result: AnalysisResult) -> str:
    """Format analysis result as human-readable text."""
    lines = []
    
    # Header
    lines.append(f"TRUG Analysis: {result.name}")
    lines.append("=" * 80)
    lines.append("")
    
    # Metadata
    lines.append("METADATA")
    lines.append(f"  Name: {result.name}")
    lines.append(f"  Version: {result.version}")
    lines.append(f"  Type: {result.type}")
    lines.append(f"  Extensions: {', '.join(result.extensions) or 'none'}")
    lines.append(f"  Vocabularies: {', '.join(result.vocabularies) or 'none'}")
    if result.description:
        lines.append(f"  Description: {result.description}")
    lines.append("")
    
    # Statistics
    lines.append("STATISTICS")
    lines.append(f"  Nodes: {result.node_count}")
    lines.append(f"  Edges: {result.edge_count}")
    lines.append(f"  Roots: {result.root_count}")
    lines.append(f"  Leaves: {result.leaf_count}")
    lines.append(f"  Avg Degree: {result.avg_degree:.2f}")
    lines.append(f"  Density: {result.density:.4f}")
    lines.append("")
    
    # Hierarchy
    lines.append("HIERARCHY")
    lines.append(f"  Max Depth: {result.max_depth}")
    lines.append(f"  Avg Depth: {result.avg_depth:.2f}")
    lines.append(f"  Branching Factor: {result.branching_factor:.2f}")
    lines.append(f"  Max Children: {result.max_children}")
    lines.append("")
    
    # Dimensions
    if result.dimensions:
        lines.append("DIMENSIONS")
        for dim_name, dim_stats in result.dimensions.items():
            lines.append(f"  {dim_name}: {dim_stats.node_count} nodes, depth {dim_stats.max_depth}")
            levels = ', '.join(f"{k}({v})" for k, v in sorted(dim_stats.metric_levels.items()))
            lines.append(f"    Levels: {levels}")
        lines.append("")
    
    # Node Types
    if result.node_type_dist:
        lines.append("NODE TYPES")
        total = sum(result.node_type_dist.values())
        for node_type, count in sorted(result.node_type_dist.items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            lines.append(f"  {node_type}: {count} ({pct:.1f}%)")
        lines.append("")
    
    # Edge Relations
    if result.edge_relation_dist:
        lines.append("EDGE RELATIONS")
        total = sum(result.edge_relation_dist.values())
        for relation, count in sorted(result.edge_relation_dist.items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            lines.append(f"  {relation}: {count} ({pct:.1f}%)")
        lines.append("")
    
    return '\n'.join(lines)
```

### JSON Formatter

```python
def format_json(result: AnalysisResult, pretty: bool = True) -> str:
    """Format analysis result as JSON."""
    data = result.to_dict()
    
    if pretty:
        return json.dumps(data, indent=2)
    else:
        return json.dumps(data)
```

### Compact Formatter

```python
def format_compact(result: AnalysisResult) -> str:
    """Format analysis result as one-line summary."""
    return (
        f"{result.name} ({result.type}): "
        f"{result.node_count} nodes, "
        f"{result.edge_count} edges, "
        f"depth {result.max_depth}"
    )
```

---

## API Design

### Python Library API

```python
from trugs_tools import analyze_trug

# Analyze from file
result = analyze_trug("example.json")

# Analyze from dict
trug = {"name": "test", ...}
result = analyze_trug(trug)

# Get formatted output
print(result.summary())
print(format_text(result))
print(format_json(result))

# Access specific statistics
print(f"Nodes: {result.node_count}")
print(f"Max Depth: {result.max_depth}")
print(f"Node Types: {result.node_type_dist}")
```

---

## CLI Design

### Command Interface

```bash
# Analyze single file (text output)
trugs-info example.json

# Analyze with JSON output
trugs-info --format json example.json

# Analyze multiple files
trugs-info file1.json file2.json file3.json

# Compact summary
trugs-info --compact example.json

# Show only specific sections
trugs-info --section metadata example.json
trugs-info --section statistics example.json
trugs-info --section hierarchy example.json
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format FORMAT` | Output format (text, json, compact) | text |
| `--section SECTION` | Show only specific section | all |
| `--output FILE` | Save output to file | stdout |

### Output Examples

**Text Output:**
```
TRUG Analysis: Python Fibonacci Example
================================================================================

METADATA
  Name: Python Fibonacci Example
  Version: 1.0.0
  Type: CODE
  Extensions: typed, scoped
  Vocabularies: python_3.12

STATISTICS
  Nodes: 42
  Edges: 38
  Roots: 1
  Leaves: 20
  Avg Degree: 1.81
  Density: 0.0220

HIERARCHY
  Max Depth: 4
  Avg Depth: 2.30
  Branching Factor: 2.10
  Max Children: 5

DIMENSIONS
  code_structure: 42 nodes, depth 4
    Levels: BASE(15), CENTI(17), DECI(10)

NODE TYPES
  STATEMENT: 20 (47.6%)
  FUNCTION: 15 (35.7%)
  MODULE: 5 (11.9%)
  CLASS: 2 (4.8%)

EDGE RELATIONS
  CONTAINS: 20 (52.6%)
  CALLS: 15 (39.5%)
  IMPORTS: 3 (7.9%)
```

**Compact Output:**
```
Python Fibonacci Example (CODE): 42 nodes, 38 edges, depth 4
```

**JSON Output:**
```json
{
  "metadata": {
    "name": "Python Fibonacci Example",
    "version": "1.0.0",
    "type": "CODE",
    "extensions": ["typed", "scoped"],
    "vocabularies": ["python_3.12"]
  },
  "statistics": {
    "nodes": 42,
    "edges": 38,
    "roots": 1,
    "leaves": 20,
    "avg_degree": 1.81,
    "density": 0.022
  },
  "hierarchy": {
    "max_depth": 4,
    "avg_depth": 2.3,
    "branching_factor": 2.1,
    "max_children": 5
  },
  "dimensions": {
    "code_structure": {
      "name": "code_structure",
      "nodes": 42,
      "max_depth": 4,
      "metric_levels": {
        "BASE": 15,
        "CENTI": 17,
        "DECI": 10
      }
    }
  },
  "distributions": {
    "node_types": {
      "STATEMENT": 20,
      "FUNCTION": 15,
      "MODULE": 5,
      "CLASS": 2
    },
    "edge_relations": {
      "CONTAINS": 20,
      "CALLS": 15,
      "IMPORTS": 3
    }
  }
}
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_analyzer.py
def test_analyze_minimal_trug():
    """Test analyzing minimal TRUG."""
    trug = load_fixture("minimal_valid.json")
    result = analyze_trug(trug)
    
    assert result.node_count == 3
    assert result.edge_count == 0
    assert result.max_depth == 2

def test_metadata_extraction():
    """Test metadata extraction."""
    trug = {
        "name": "Test TRUG",
        "version": "1.0.0",
        "type": "CODE",
        "capabilities": {
            "extensions": ["typed"],
            "vocabularies": ["python_3.12"],
            "profiles": []
        },
        "nodes": [],
        "edges": []
    }
    
    result = analyze_trug(trug)
    assert result.name == "Test TRUG"
    assert result.extensions == ["typed"]

def test_hierarchy_analysis():
    """Test hierarchy analysis."""
    trug = load_fixture("complex_hierarchy.json")
    result = analyze_trug(trug)
    
    assert result.max_depth > 0
    assert result.branching_factor > 0
```

### Integration Tests

```python
# tests/test_analyzer_integration.py
def test_analyze_all_branches():
    """Test analyzing all branch examples."""
    branches = ["web", "writer"]
    
    for branch in branches:
        trug = load_fixture(f"{branch}_minimal.json")
        result = analyze_trug(trug)
        
        assert result.node_count > 0
        assert result.type in ["WEB", "WRITER"]

def test_output_formats():
    """Test all output formats."""
    trug = load_fixture("python_minimal.json")
    result = analyze_trug(trug)
    
    text = format_text(result)
    assert "METADATA" in text
    
    json_str = format_json(result)
    data = json.loads(json_str)
    assert "metadata" in data
    
    compact = format_compact(result)
    assert result.name in compact
```

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `analyzer.py` with `analyze_trug()` function
- [ ] Create `AnalysisResult` and `DimensionStats` classes
- [ ] Implement metadata extraction
- [ ] Implement graph statistics computation

### Phase 2: Analysis Functions
- [ ] Implement `analyze_dimensions()`
- [ ] Implement `analyze_hierarchy()`
- [ ] Implement `compute_distributions()`
- [ ] Add helper functions (depth computation, etc.)

### Phase 3: Output Formatters
- [ ] Implement `format_text()`
- [ ] Implement `format_json()`
- [ ] Implement `format_compact()`

### Phase 4: CLI
- [ ] Create CLI argument parser
- [ ] Implement file loading
- [ ] Add format options
- [ ] Add section filtering
- [ ] Add `--help` documentation

### Phase 5: Testing
- [ ] Write unit tests for each analysis function
- [ ] Write tests for formatters
- [ ] Write integration tests
- [ ] Write CLI tests
- [ ] Achieve >90% code coverage

### Phase 6: Documentation
- [ ] Write API documentation
- [ ] Write CLI usage guide
- [ ] Add examples with sample output

---

## Dependencies

### Required
- Python 3.8+
- Standard library (json, dataclasses, statistics)

### Testing
- pytest
- pytest-cov

---

## Future Enhancements

**Not in v1.0, but valuable for future versions:**

1. **Visual Output** - Generate ASCII art tree diagrams
2. **Comparison Mode** - Compare two TRUGs side-by-side
3. **Trend Analysis** - Track TRUG evolution over time
4. **Complexity Metrics** - Cyclomatic complexity, coupling metrics
5. **Query Mode** - Filter analysis by dimension, node type, etc.
6. **Export Formats** - CSV, Markdown, HTML reports
7. **Integration** - CI/CD integration for tracking metrics

---

## Specification Status

✅ **Complete** - Ready for implementation

**Next Steps:**
1. Review this specification
2. Implement Phase 1: Core Infrastructure
3. Implement analysis functions
4. Add formatters and CLI

---

## References

- [TRUGS_PROTOCOL/SCHEMA.md](../TRUGS_PROTOCOL/SCHEMA.md) - Complete schema reference
- [SPEC_validator.md](SPEC_validator.md) - Validator specification
- [AAA.md](AAA.md) - TRUGS_TOOLS project overview
