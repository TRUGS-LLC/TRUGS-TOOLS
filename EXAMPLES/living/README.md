# Living Branch Examples

LIVING branch examples for agentic memory and retrieval-augmented workflows using TRUGS v1.0.

## Files

| File | Complexity | Nodes | Description |
|------|-----------|-------|-------------|
| `simple.json` | Simple | 3 | Query triggers a tool execution that produces an entity |
| `medium.json` | Medium | 5 | Query triggers two tools, extracts an entity, and produces an answer |
| `complex.json` | Complex | 9 | Multi-query research with synthesis across multiple data sources |

## Node Types

- **QUERY** — User question or information request
- **TOOL_EXECUTION** — Invocation of an external tool or API
- **ENTITY** — Extracted data or fact from a tool execution
- **SYNTHESIS** — Aggregation or comparison of multiple entities
- **ANSWER** — Final response to a query

## Edge Types

- **triggers** — Query triggers a tool execution
- **produces** — Tool execution produces an entity
- **synthesizes_to** — Entity feeds into a synthesis node
- **builds_on** — A node builds on prior results
- **cites** — Answer cites a source entity
- **contains** — Parent-child containment

## Dimensions

```
memory_flow: QUERY → TOOL_EXECUTION → ENTITY → SYNTHESIS → ANSWER
```

## Usage

```bash
# Validate
trugs-validate living/medium.json

# Generate
trugs-generate --branch living --template simple
```

## Specification

See [BRANCH_SPECS/](../../BRANCH_SPECS/) for branch specifications.
