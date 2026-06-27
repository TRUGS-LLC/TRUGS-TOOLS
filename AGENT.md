# TRUGS Tools — Agent Orientation

You are reading the entry point for LLM agents consuming this repository.

## Role

TRUGS-TOOLS is the **reference language toolchain** of the TRUGS-LLC portfolio:
the `trug` CLI and the CORE validator that the rest of the commons imports and
that the public most directly installs. For the specification and pedagogy, see:

- TRUGS-LLC/TRUGS — the spec (CORE + TRL + reference papers) and the getting-started guide

## Package

- PyPI: `pip install trugs-tools`
- Single binary: `trug`
- Python module: `trugs_tools`

## Command surface (run `trug --help` for the canonical list)

Eight verbs on the `trug` binary — no god-command-tree, no hidden sub-namespaces.
This public wheel ships the language tier only:

```
trug validate     Validate a TRUG JSON file against the 12 structural rules
trug trl          Compile / decompile / validate TRL <-> TRUG
trug get          Read full content of a node in a TRUG graph
trug update       Update properties on an existing node
trug delete       Remove nodes and their connected edges
trug unlink       Remove specific edges from a TRUG graph
trug compliance   Dark Code compliance check over a source tree
trug audit        Corpus-side audit bridges (markdown / vocab)
```

Run `trug <verb> --help` for verb-specific usage, examples, and exit codes.

## Navigation

- `src/trugs_tools/` — the `trug` CLI + CORE validator implementation
- `src/trugs_tools/internal/` — maintainer utilities (not `trug` subcommands; invoke via `python -m ...`)
- `trugs-folder/` — the sibling cartography package (binary: `trug-a-folder`) and its bundled suite

## Spec dependencies

- CORE (7 node fields + 3 edge fields): `TRUGS-LLC/TRUGS/TRUGS_PROTOCOL/CORE.md`
- TRL (the constrained-English vocabulary across 9 parts of speech): `TRUGS-LLC/TRUGS/TRUGS_LANGUAGE/`
