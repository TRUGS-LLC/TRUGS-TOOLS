# TRUGS Examples Gallery

Complete examples for all **5 TRUGS branches** (2 core + 3 advanced) plus cross-branch interaction examples, demonstrating the TRUGS v1.0 specification.

**Total Examples:** 19 validated JSON files across 5 branches + cross-branch

## Example Tiers

| Tier | Description | Typical Nodes |
|------|-------------|---------------|
| `minimal.json` / `simple.json` | Minimal structure (3 nodes) | 3 |
| `medium.json` | Medium complexity with relationships | 5–9 |
| `complete.json` | All branch features demonstrated | 5–10 |
| `complex.json` | Rich cross-references, hierarchy | 8–15 |
| `si_levels.json` | SI-prefix metric levels (DEKA, KILO, BASE, MILLI) | 5–7 |

## Core Branches (2)

| Branch | Type | Examples | Node Types |
|--------|------|----------|------------|
| [web/](web/) | WEB | 4 (minimal, medium, complex, complete) | SITE, PAGE, SECTION |
| [writer/](writer/) | WRITER | 4 (minimal, medium, complex, complete) | DOCUMENT, SECTION, PARAGRAPH, CITATION, REFERENCE |

## Advanced Branches (3)

| Branch | Type | Examples | Node Types |
|--------|------|----------|------------|
| [orchestration/](orchestration/) | ORCHESTRATION | 4 (simple, medium, complex, si_levels) | AGENT, PRINCIPAL, RESOURCE, PERMISSION, TASK, ESCALATION |
| [living/](living/) | LIVING | 3 (simple, medium, complex) | QUERY, ANSWER, ENTITY, TOOL_EXECUTION, SYNTHESIS |
| [knowledge/](knowledge/) | KNOWLEDGE | 3 (simple, medium, complex) | CONCEPT, ENTITY, CLASS, INSTANCE |

## Cross-Branch Examples

| Example | Branches | Description | Nodes |
|---------|----------|-------------|-------|
| [cross_branch/knowledge_executable.json](cross_branch/knowledge_executable.json) | knowledge + executable | Task pipeline querying medical ontology | 9 |

## SI-Prefix Metric Levels

Examples demonstrating the modern `{SI_PREFIX}_{NAME}` format instead of legacy `MINIMAL`/`STANDARD`:
- `orchestration/si_levels.json` — uses HECTO_PRINCIPAL, DEKA_AGENT, KILO_RESOURCE, BASE_TASK, MILLI_PERMISSION

## All Examples Are Valid

Every example in this folder has been validated against the TRUGS v1.0 specification:
- All 9 validation rules pass
- All required fields present
- All edge relationships consistent
- 100% validation pass rate (19/19)

## Using These Examples

### Validate an example:
```bash
trugs-validate python/minimal.json
trugs-validate orchestration/simple.json
```

### View information:
```bash
trugs-info python/complete.json
```

### Generate similar examples:
```bash
trugs-generate --branch python --template minimal
trugs-generate --branch orchestration --template complete
```

## Specification

Full specification details available in parent directory:
- [SPEC_validator.md](../SPEC_validator.md)
- [SPEC_generator.md](../SPEC_generator.md)
- [SPEC_analyzer.md](../SPEC_analyzer.md)
- [SPEC_cli.md](../SPEC_cli.md)
- [BRANCH_SPECS/](../BRANCH_SPECS/)
