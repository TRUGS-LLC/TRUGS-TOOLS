# Changelog

All notable changes to `trugs-tools` will be documented here. Format: [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] — 2026-04-18

### Added

Initial release. Single `tg` binary with git-style nested subparsers consolidating what was previously shipped across 3 separate source trees.

**Architecture:**
- Single entry point: `tg = "trugs_tools.cli:main"` in pyproject
- Nested subparser tree: 21 top-level verbs + 4 sub-namespaces (`memory`, `aaa`, `epic`, `render`) = ~36 operations
- Replaces the flat `trugs-*` CLI family from pre-1.0 development

**Top-level verbs (21):**
- Lifecycle: `init`, `check`, `sync`, `render`, `validate`
- Inspection: `info`, `ls`, `where`, `find`
- CRUD: `add`, `get`, `update`, `delete`, `mv`, `link`, `unlink`, `dim`
- Special: `compliance`, `trl`, `export`, `import`

**Sub-namespaces (4):**
- `tg memory` — `remember`, `recall`, `forget`, `associate`, `render`, `audit`, `import`, `reconcile`
- `tg aaa` — `generate`, `validate`
- `tg epic` — `sync`
- `tg render` — `architecture` (default), `agent`, `claude`, `aaa`

**Sources consolidated:**
- `TRUGS-DEVELOPMENT/TRUGS_TOOLS_development/` — folder lifecycle CLIs, branch schemas, templates, web pipeline
- `TRUGS-LLC/TRUGS/tools/` — memory subsystem (4 CLIs), TRL compiler, compliance_check, tget/tupdate/tdelete/tunlink (5 ops migrated; `trugs` 2.0.0 drops these — use `tg <op>` now)
- `Xepayac/TRUGS-AAA` — aaa_validator now exposed as `tg aaa validate` (archived after migration)

**Internal utilities (not exposed via `tg`):**
- `trugs_tools/internal/build_language_trug.py` — maintainer utility for rebuilding TRL vocabulary. Invoke via `python -m trugs_tools.internal.build_language_trug`.

**Breaking change migration from pre-1.0 CLIs:**

| Old (flat) | New (unified) |
|---|---|
| `trugs-folder-check` | `tg check` |
| `trugs-folder-init` | `tg init` |
| `trugs-folder-sync` | `tg sync` |
| `trugs-folder-render` | `tg render` |
| `trugs-folder-map` | `tg info` (with map flag) |
| `trugs-epic-sync` | `tg epic sync` |
| `trugs-memory` | `tg memory` |
| `trugs-memory-render` | `tg memory render` |
| `trugs-memory-audit` | `tg memory audit` |
| `trugs-memory-import` | `tg memory import` |
| `trugs-memory reconcile` | `tg memory reconcile` |
| `trugs-memory associate` | `tg memory associate` |
| `trugs-trl` | `tg trl` |
| `trugs-compliance-check` | `tg compliance` |
| `trugs-validate` | `tg validate` |
| `trugs-tget` | `tg get` |
| `trugs-tupdate` | `tg update` |
| `trugs-tdelete` | `tg delete` |
| `trugs-tunlink` | `tg unlink` |
| `trugs-tadd/tls/tcd/tfind/tmove/tlink/tdim/twatch/tsync/twhere` | `tg add/ls/...` |
| `aaa-validate` (Xepayac/TRUGS-AAA) | `tg aaa validate` |
| `trugs-aaa-generate` | `tg aaa generate` |
| `trugs-agent-render` | `tg render agent` |
| `trugs-claude-render` | `tg render claude` |

Ref: TRUGS-LLC/TRUGS-DEVELOPMENT#1576 (portfolio reorg EPIC)
