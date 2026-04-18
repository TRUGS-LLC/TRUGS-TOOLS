# Writer Branch Examples

WRITER branch examples for document structure representation using TRUGS v1.0.

## Files

| File | Complexity | Nodes | Description |
|------|-----------|-------|-------------|
| `minimal.json` | Minimal | 3 | Single document with one section |
| `medium.json` | Medium | 7 | Research paper with introduction, methodology, citation, and reference |
| `complex.json` | Complex | 15 | Survey paper with abstract, multiple sections, citations, and cross-references |
| `complete.json` | Complete | Many | Full-featured example with all node types |

## Node Types

- **DOCUMENT** — Top-level document with title, author, date
- **SECTION** — Document section with ordering
- **PARAGRAPH** — Text content
- **CITATION** — In-text citation
- **REFERENCE** — Bibliography entry

## Dimensions

```
document_structure: DOCUMENT → SECTION → PARAGRAPH
```

## Usage

```bash
# Validate
trugs-validate writer/medium.json

# Generate
trugs-generate --branch writer --template minimal
```

## Specification

See [BRANCH_SPECS/REFERENCE_writer.md](../../BRANCH_SPECS/REFERENCE_writer.md) for the full Writer branch specification.
