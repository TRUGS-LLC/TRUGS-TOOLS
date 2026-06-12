# TRUGS Tools

**The TRUGS language CLI.** One binary, `trug` — validate TRUG graphs, compile
and decompile TRL, graph-node CRUD, Dark Code compliance, and corpus audit.
Implements TRUGS 2.0 (`core_v2.0.0`).

TRUG/L (TRL) is a constrained subset of English: every valid sentence compiles
to a graph and every graph decompiles back to the sentence, losslessly. You
write TRL when communicating; you store and validate TRUGS (the JSON graph)
when executing. The sentence is the graph.

## Install

```bash
pip install trugs-tools
```

## Quickstart

```bash
trug --help                          # the verb list, one summary per verb
trug validate first.trug.json        # the 12 structural rules -> VALID / INVALID
trug trl compile hello.trl           # TRL sentence -> TRUG graph
trug trl decompile hello.trug.json   # graph -> the sentence, losslessly
trug compliance src/                 # Dark Code compliance scan
```

New to TRUGS? The five-minute on-ramp:
**[GETTING_STARTED.md](https://github.com/TRUGS-LLC/TRUGS/blob/main/GETTING_STARTED.md)**

## Command surface

Eight verbs on the `trug` binary:

| verb | what it does |
|------|--------------|
| `validate` | Validate a TRUG JSON file against the 12 structural rules |
| `trl` | Compile / decompile / validate TRL ↔ TRUG |
| `get` | Read full content of a node in a TRUG graph |
| `update` | Update properties on an existing node |
| `delete` | Remove nodes and their connected edges |
| `unlink` | Remove specific edges from a TRUG graph |
| `compliance` | Dark Code compliance check over a source tree |
| `audit` | Corpus-side audit bridges (markdown / vocab) |

Every verb documents examples and exit codes: `trug <verb> --help`.

Folder cartography — keeping a directory tree and its TRUG graph in sync and
rendering `ARCHITECTURE.md` — is the sibling package
[`trugs-folder`](./trugs-folder/) (binary: `trug-a-folder`).

## Role in the TRUGS-LLC portfolio

- **[TRUGS](https://github.com/TRUGS-LLC/TRUGS)** — the specification (CORE + TRL + reference papers) and the [getting-started guide](https://github.com/TRUGS-LLC/TRUGS/blob/main/GETTING_STARTED.md).
- **TRUGS-TOOLS** (this repo) — the language CLI `trug` (this package) + the cartography tool `trug-a-folder` ([trugs-folder/](./trugs-folder/)).
- **[TRUGS-STORE](https://github.com/TRUGS-LLC/TRUGS-STORE)** — the swappable graph-storage backend both tools sit on.

## Documentation

- [CHANGELOG.md](./CHANGELOG.md) — version history, including the 2.0 boundary statement and the v1 migration table
- [GETTING_STARTED.md](https://github.com/TRUGS-LLC/TRUGS/blob/main/GETTING_STARTED.md) — the on-ramp
- [SECURITY.md](./SECURITY.md) · [CONTRIBUTING.md](./CONTRIBUTING.md)

## Development

```bash
make dev      # install dev/test tooling
make check    # the Tier-1 gate — secrets / format / lint / types / tests + self-validation
```

The last `make check` step is Layer-4 self-description: the engine validates
the repo's own `folder.trug.json` against the TRUGS CORE rules it implements.

## License

Apache-2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
