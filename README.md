# TRUGS Tools

**The TRUGS language CLI.** One binary, `trug` — validate TRUG graphs, compile
and decompile TRL, graph-node CRUD, Dark Code compliance, and corpus audit.
Implements TRUGS 2.0 (`core_v2.0.0`).

TRUG/L (TRL) is a constrained subset of English. For the syntax this compiler
supports, compilation returns a CORE-valid TRUG graph or fails. Decompilation
adds generated-looking identifiers only when needed for graph identity. For
compiled sources, defined-term stative clauses follow their definitions and
retain stative and conjunction edge occurrences. Node type checks apply only to edge
endpoints or operation nodes, independently of hierarchy fields. Every edge
relation is checked; unsupported rendered words or uncompilable output cause
failure. Successful decompilation returns canonical TRL that compiles.
The compilable source contracts and `hello.trl` preserve node identifiers, node
types and edge triples in the round trip. Sugar, original formatting and arbitrary
JSON properties need not be preserved. Write TRL when communicating; store and
validate TRUGS (the JSON graph) when executing.

## Install

```bash
pip install trugs-tools
```

## Quickstart

```bash
trug --help                          # the verb list, one summary per verb
trug validate first.trug.json        # the 16 CORE rules -> VALID / INVALID
trug trl compile hello.trl > hello.trug.json   # TRL sentence -> TRUG graph (saved to file)
trug trl decompile hello.trug.json             # graph -> compilable canonical TRL, or an error
trug compliance src/                 # Dark Code compliance scan
```

New to TRUGS? The five-minute on-ramp:
**[GETTING_STARTED.md](https://github.com/TRUGS-LLC/TRUGS/blob/main/GETTING_STARTED.md)**

## Command surface

Eight verbs on the `trug` binary:

| verb | what it does |
|------|--------------|
| `validate` | Validate a TRUG JSON file against the 16 CORE rules |
| `trl` | Compile / decompile / validate TRL ↔ TRUG |
| `get` | Read full content of a node in a TRUG graph |
| `update` | Update properties on an existing node |
| `delete` | Remove nodes and their connected edges |
| `unlink` | Remove specific edges from a TRUG graph |
| `compliance` | Dark Code compliance check over a source tree |
| `audit` | Corpus-side audit bridges (markdown / vocab) |

Every verb documents examples and exit codes: `trug <verb> --help`.
For `trug trl`, content syntax, grammar, vocabulary and validation failures exit 1;
usage errors (bad arguments, missing or unreadable files, or expected JSON) exit 2.

## Role in the TRUGS-LLC portfolio

- **[TRUGS](https://github.com/TRUGS-LLC/TRUGS)** — the specification (CORE + TRL + reference papers) and the [getting-started guide](https://github.com/TRUGS-LLC/TRUGS/blob/main/GETTING_STARTED.md).
- **TRUGS-TOOLS** (this repo) — the language CLI `trug` (this package).
- **[TRUGS-STORE](https://github.com/TRUGS-LLC/TRUGS-STORE)** — the swappable graph-storage backend used by the language CLI.

## Documentation

- [CHANGELOG.md](./CHANGELOG.md) — version history, including the 2.0 boundary statement and the v1 migration table
- [GETTING_STARTED.md](https://github.com/TRUGS-LLC/TRUGS/blob/main/GETTING_STARTED.md) — the on-ramp
- [SECURITY.md](./SECURITY.md) · [CONTRIBUTING.md](./CONTRIBUTING.md)

## Development

```bash
make dev      # editable install of the trug CLI with test dependencies (.[test])
make check    # pytest tests/, then trug validate folder.trug.json
```

The last `make check` step is Layer-4 self-description: the engine validates
the repo's own `folder.trug.json` against the TRUGS CORE rules it implements.

## Scope

This software does not include self-modifying TRUGS: graphs that change their
own structure while they run.

## License

Apache-2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
