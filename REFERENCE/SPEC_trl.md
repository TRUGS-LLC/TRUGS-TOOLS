# SPEC: `tg trl` — TRL (TRUG/L) compiler

**Version:** 1.0.0
**Top-level command:** `tg trl`
**Python module:** `trugs_tools.trl`

## Purpose

TRUG/L (TRL) is the 190-word formalized subset of English used to describe executable TRUG operations. Every valid TRL sentence compiles to a directed graph. `tg trl` is the compiler and linter for TRL source.

## Vocabulary

TRUG/L is a closed 190-word vocabulary across 8 parts of speech:

| Part of speech | Count |
|---|---|
| Nouns (things) | 26 |
| Verbs (actions) | 61 |
| Adjectives (node properties) | 36 |
| Adverbs (operation properties) | 19 |
| Prepositions (edge relations) | 18 |
| Conjunctions | 13 |
| Articles | 11 |
| Pronouns | 6 |

Canonical source: `TRUGS-LLC/TRUGS/TRUGS_LANGUAGE/language.trug.json`.

Bundled copy: `src/trugs_tools/data/language.trug.json` (package data). The bundled copy tracks the canonical source; `python -m trugs_tools.internal.build_language_trug` regenerates it from `TRUGS/TRUGS_LANGUAGE/SPEC_vocabulary.md`.

## Command

### `tg trl`

```
tg trl FILE [flags]
```

Two operating modes, auto-detected from file contents:

**Mode 1 — Compile (`.trl` source or `<trl>` blocks in Markdown)**

Input: TRL sentences, one per line or one per `<trl>...</trl>` block.

Output (default stdout): compiled TRUG graph as JSON.

```bash
# Compile a standalone .trl file
tg trl my_rules.trl > my_rules.trug.json

# Extract + compile TRL blocks from a Markdown file
tg trl CLAUDE.md > claude_rules.trug.json
```

**Mode 2 — Validate / lint**

```bash
# Validate all TRL blocks in a file (exit 0 if clean)
tg trl --validate CLAUDE.md

# Strict mode: exit 1 on any unknown word
tg trl --strict CLAUDE.md
```

## Flags

| Flag | Purpose |
|---|---|
| `--validate` | Parse-only; no JSON output. Exit 0 if all TRL sentences valid. |
| `--strict` | Treat vocabulary warnings as errors. |
| `--format {json,compact,pretty}` | JSON output style (default: `pretty`). |
| `--output PATH` | Write to file instead of stdout. |
| `--language PATH` | Override bundled `language.trug.json` (advanced). |

## Sentence anatomy

A TRL sentence compiles by:

1. **Stripping sugar words** (OF, IS, ARE, BE, BEEN, HAS, HAVE, WILL, THAT, etc.)
2. **Identifying parts of speech** — each token must be in the 190-word vocabulary, or a proper identifier (lowercase with underscores, or a domain-specific noun).
3. **Building the clause tree** — subject (Actor), modal (SHALL/MAY/SHALL_NOT), verb, objects, prepositions.
4. **Emitting graph fragments** — Actors → nodes; verbs → operation nodes; prepositions → edges.

Example input:

```
PARTY system SHALL FILTER ALL ACTIVE RECORD THEN WRITE RESULT TO ENDPOINT output.
```

Compiled output (simplified):

```json
{
  "nodes": [
    {"id": "system", "type": "PARTY"},
    {"id": "op_filter", "type": "TRANSFORM", "properties": {"op": "FILTER", "scope": "ALL", "filter": "ACTIVE"}},
    {"id": "op_write", "type": "MOVE", "properties": {"op": "WRITE"}},
    {"id": "output", "type": "ENDPOINT"}
  ],
  "edges": [
    {"from_id": "op_filter", "to_id": "op_write", "relation": "THEN"},
    {"from_id": "op_write", "to_id": "output", "relation": "TO"}
  ]
}
```

## Modal rules

- `SHALL` — mandatory; subject MUST perform the verb. Violations are failures.
- `MAY` — permitted; subject may or may not perform the verb.
- `SHALL_NOT` — prohibited; subject MUST NOT perform the verb.

Modals require **Actor subjects** (PARTY, AGENT, PROCESS, SERVICE, FUNCTION, TRANSFORM, PRINCIPAL). Non-Actor subjects (DATA, RECORD, FILE) with modals fail validation.

## Grammar errors

`tg trl` emits structured diagnostics with line/column:

```
ERROR: line 3, col 12 — unknown word 'SCHEDULE' (not in 190-word vocabulary)
ERROR: line 5, col 1 — modal SHALL requires Actor subject; got 'DATA'
WARNING: line 7 — sugar word 'PLEASE' (no-op; stripped)
```

## Common use cases

**Linting CLAUDE.md rules:**

```bash
tg trl --validate --strict CLAUDE.md
```

**Compiling a spec to a TRUG:**

```bash
tg trl spec.trl --output spec.trug.json
```

**Auditing a codebase's TRL coverage:**

```bash
# combined with tg compliance
tg compliance . --include-trl
```

## Integration with the Dark Code standard

Per `STANDARD_dark_code_compliance.md` (in the TRUGS spec repo):

- **C1** — every public function has a TRUG/L comment that **parses via `tg trl --validate`**
- **C4** — every test function has an `AGENT SHALL VALIDATE ...` TRL sentence that **parses via `tg trl --validate`**

`tg compliance` invokes `tg trl --validate` on every source file; failure to parse is a compliance violation.

## See also

- [`SPEC_cli.md`](./SPEC_cli.md) — full `tg` CLI surface
- [`SPEC_compliance.md`](./SPEC_compliance.md) — Dark Code compliance check (uses `tg trl` internally)
- TRUGS-LLC/TRUGS/TRUGS_LANGUAGE/ — canonical vocabulary + grammar spec
