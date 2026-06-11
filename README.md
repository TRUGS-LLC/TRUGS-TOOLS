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

## Development — the Tier-1 gate

One command reads GREEN across the release-polish layers (AAA #1976 Phase 7 / #2190):

```bash
make dev      # install dev/test tooling (ruff, mypy, pytest + extras)
make check    # the Tier-1 gate — secrets / format / lint / types / tests + Layer-4
```

`make check` runs, in order: `gitleaks` (secrets) · `ruff format --check` · `ruff check` ·
`mypy` · `pytest` · **`tg validate`** on the repo's own `folder.trug.json` + every
`EXAMPLES/**` TRUG. That last step is **Layer-4 self-description** — the engine validates
its own graph against TRUGS's 16-rule CORE. `tests/test_validator_self_coherence.py`
guards the invariant that the `tg validate` CLI and the in-process `validate_trug()`
function always return the same verdict, so no Layer-4 result ships on an incoherent
validator. The lint/type/test scope is the core engine + `filesystem/` CLI today and
widens as the remaining subpackages reach the same bar.

## License

Apache-2.0 — see [LICENSE](./LICENSE)
