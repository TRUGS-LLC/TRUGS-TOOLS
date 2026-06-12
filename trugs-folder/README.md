# trugs-folder

**TRUGS cartography.** One binary, `trug-a-folder` — keep a directory tree and
its TRUG graph in sync, validate it against the folder governance rules, and
render a human-readable `ARCHITECTURE.md` from it. Implements TRUGS 2.0
(`core_v2.0.0`).

The idea: the folder *is* a graph. `folder.trug.json` holds one node per file,
typed by the governance vocabulary (code is `COMPONENT`, prose is `DOCUMENT`),
and the tool keeps that graph honest as the directory changes.

## Install

```bash
pip install trugs-folder
```

## Quickstart

```bash
trug-a-folder init myproject --scan -d "My first mapped folder"
trug-a-folder check myproject
trug-a-folder render architecture myproject
trug-a-folder sync myproject        # reconcile after files change
```

New to TRUGS? The five-minute on-ramp:
**[GETTING_STARTED.md](https://github.com/TRUGS-LLC/TRUGS/blob/main/GETTING_STARTED.md)**

## Command surface

Fourteen verbs on the `trug-a-folder` binary:

| verb | what it does |
|------|--------------|
| `init` | Initialize `folder.trug.json` in a directory |
| `check` | Validate against the governance rules |
| `sync` | Reconcile the graph with the filesystem |
| `render` | Render `ARCHITECTURE.md` from the graph |
| `info` | Show summary information about a TRUG file |
| `ls` | List directory contents with TRUG metadata |
| `where` | Search all folder graphs for a concept, node, or file |
| `find` | Query nodes by type / name / dimension |
| `add` | Add files to the graph |
| `mv` | Move/rename a node |
| `link` | Create or remove typed edges between nodes |
| `dim` | Manage dimensions |
| `export` | Export `folder.trug.json` from the database |
| `import` | Import `folder.trug.json` into the database |

Every verb documents examples and exit codes: `trug-a-folder <verb> --help`.

The language CLI — validating arbitrary TRUG graphs and compiling TRL — is the
sibling package [`trugs-tools`](https://github.com/TRUGS-LLC/TRUGS-TOOLS)
(binary: `trug`), which this package builds on.

## Lineage

This package descends from the cartography half of `trugs-tools` 1.0.0; the
2.0 release split it onto its own wheel. History is in
[CHANGELOG.md](CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
