# TRUGS Tools — Agent Orientation

You are reading the entry point for LLM agents consuming this repository.

## Role

TRUGS-TOOLS is **reference + implementation** in the TRUGS-LLC portfolio. It provides all CLIs needed to operate on TRUGs. For spec + pedagogy, see:

- TRUGS-LLC/TRUGS (spec: CORE + TRL + papers)
- TRUGS-LLC/TRUGS-AGENT (marketing hub + concept tutorials with examples)

## Package

- PyPI: `pip install trugs-tools`
- Single binary: `tg`
- Python module: `trugs_tools`

## Command tree (see `tg --help` for canonical)

```
tg init|check|sync|render|validate|info|ls|where|find|add|get|update|delete|mv|link|unlink|dim|compliance|trl|export|import
tg memory <remember|recall|forget|associate|render|audit|import|reconcile>
tg aaa <generate|validate>
tg epic <sync>
tg render <architecture|agent|claude|aaa>
```

## Navigation

- `src/trugs_tools/` — CLI implementation
- `src/trugs_tools/internal/` — maintainer utilities (not `tg` subcommands; invoke via `python -m ...`)
- `branches/` — experimental branch vocabularies (CORE covers most cases)
- `tests/` — unit + integration tests
- `REFERENCE/` — SPEC_*.md docs for each tool
- `EXAMPLES/` — runnable examples (schema-validation fixtures)

## Spec dependencies

- CORE (7 node fields + 3 edge fields): `TRUGS-LLC/TRUGS/TRUGS_PROTOCOL/CORE.md`
- TRL (190-word vocabulary): `TRUGS-LLC/TRUGS/TRUGS_LANGUAGE/`
