# Cross-Branch Examples

Multi-branch TRUG examples demonstrating interaction patterns between different branch domains.

## Purpose

These examples validate that TRUGS can represent systems spanning multiple domains — combining node types, edge relations, and dimensions from different branches in a single graph.

## Examples

| File | Branches | Description | Nodes | Edges |
|------|----------|-------------|-------|-------|
| `python_orchestration.json` | python + orchestration | Agent generating and reviewing Python code | 9 | 13 |

## Key Patterns

### Python + Orchestration
- **Agent hierarchy** (PRINCIPAL → AGENT → TASK) manages **code hierarchy** (MODULE → CLASS → FUNCTION)
- Tasks delegate code generation and review between agents
- Generated code lives under the generating task's containment



## Multi-Dimensional Structure

Cross-branch examples declare multiple dimensions:
```json
"dimensions": [
  {"name": "agent_hierarchy", "levels": ["PRINCIPAL", "AGENT", "TASK"]},
  {"name": "code_structure", "levels": ["MODULE", "CLASS", "FUNCTION"]}
]
```

## Validation

All cross-branch examples pass TRUGS v1.0 validation (9 rules, 0 errors, 0 warnings).
