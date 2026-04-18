# Knowledge Branch Examples

KNOWLEDGE branch examples for ontological modeling and knowledge graphs using TRUGS v1.0.

## Files

| File | Complexity | Nodes | Description |
|------|-----------|-------|-------------|
| `simple.json` | Simple | 3 | Class with an entity and an instance |
| `medium.json` | Medium | 5 | Two classes with entities and an instance showing ontological relationships |
| `complex.json` | Complex | 8 | Multi-class medical ontology with concepts, entities, and instances |

## Node Types

- **CLASS** — Abstract category in an ontology
- **ENTITY** — Named member of a class
- **CONCEPT** — Abstract idea or principle
- **INSTANCE** — Concrete instance of an entity

## Edge Types

- **is_a** — Subtype or membership relationship
- **has_property** — Entity has a property or attribute
- **part_of** — Component relationship
- **causes** — Causal relationship between concepts/entities
- **related_to** — General semantic association
- **contains** — Parent-child containment

## Dimensions

```
ontology_hierarchy: CLASS → ENTITY → INSTANCE
```

## Usage

```bash
# Validate
trugs-validate knowledge/medium.json

# Generate
trugs-generate --branch knowledge --template simple
```

## Specification

See [BRANCH_SPECS/](../../BRANCH_SPECS/) for branch specifications.
