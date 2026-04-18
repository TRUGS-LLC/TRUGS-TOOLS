# TRUGS Tools

**CLI toolkit for the TRUGS specification.** One binary `tg` with git-style nested subcommands — validation, generation, memory, folder lifecycle, AAA protocol, and more.

## Install

```bash
pip install trugs-tools
```

## Quickstart

```bash
tg --help                # see all commands
tg init my-project       # create folder.trug.json
tg check                 # validate it
tg compliance .          # Dark Code compliance scan
tg memory remember ~/.../memory.trug.json "decision text" --type project --rule "terse"
tg aaa validate my-issue.aaa.md
```

## Command surface

36 operations under one binary:

- **Lifecycle:** `init`, `check`, `sync`, `render`, `validate`
- **Inspection:** `info`, `ls`, `where`, `find`
- **CRUD:** `add`, `get`, `update`, `delete`, `mv`, `link`, `unlink`, `dim`
- **Special:** `compliance`, `trl`, `export`, `import`
- **Memory:** `tg memory <sub>` — 8 subs including remember/recall/forget/associate/render/audit/import/reconcile
- **AAA:** `tg aaa <sub>` — generate, validate
- **EPIC:** `tg epic sync`

## Role in the TRUGS-LLC portfolio

- **[TRUGS](https://github.com/TRUGS-LLC/TRUGS)** — spec (CORE + TRL + reference papers). Zero CLIs, zero code.
- **[TRUGS-AGENT](https://github.com/TRUGS-LLC/TRUGS-AGENT)** — marketing hub + orientation (concept folders with examples). Zero install to read.
- **TRUGS-TOOLS** (this repo) — reference + implementation (CLIs + schemas + tests). Install when you want automation.
- **[TRUGS-STORE](https://github.com/TRUGS-LLC/TRUGS-STORE)** — swappable graph storage backend.

## Documentation

- [CHANGELOG.md](./CHANGELOG.md) — version history
- [REFERENCE/](./REFERENCE/) — SPEC_*.md docs for each tool
- [branches/](./branches/) — experimental branch vocabularies

## License

Apache-2.0 — see [LICENSE](./LICENSE)
