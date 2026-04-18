# SPEC: `tg` — TRUGS CLI

**Version:** 1.0.0
**Binary:** `tg`
**Package:** `trugs-tools`
**Python module:** `trugs_tools.cli`

## Overview

`tg` is the unified command-line interface for the TRUGS specification. One binary, git-style nested subcommands, 36 operations under 21 top-level verbs + 4 sub-namespaces.

Design pattern follows `git`, `docker`, `kubectl`, `gh`: one namespace declares TRUG-ness; every subcommand operates on TRUGs. Anything outside this namespace is plain file I/O.

## Install

```bash
pip install trugs-tools
```

Ships a single entry point:

```toml
[project.scripts]
tg = "trugs_tools.cli:main"
```

Runtime dependency: `trugs-store>=0.1.0` (swappable graph storage backend). No dependency on the `trugs` PyPI package — see `principle_spec_is_data` in the TRUGS-DEVELOPMENT EPIC.

## Command surface

### Top-level verbs (21)

**Lifecycle (5)**

| Command | Purpose |
|---|---|
| `tg init [DIR]` | Create `folder.trug.json` in cwd or DIR. |
| `tg check [PATH]` | Validate TRUG structurally (default: `./folder.trug.json`). |
| `tg sync [PATH]` | Sync TRUG with filesystem reality — add new-file nodes; mark missing-file nodes stale. |
| `tg render [TARGET]` | Render TRUG to output file. TARGET ∈ `{architecture, agent, claude, aaa}` (default: `architecture`). |
| `tg validate [PATH]` | CORE 16-rule structural validator. For AAA protocol validation see `tg aaa validate`. |

**Inspection (4)**

| Command | Purpose |
|---|---|
| `tg info NODE` | Show node metadata + incident edges. |
| `tg ls [SCOPE]` | List nodes in TRUG. |
| `tg where NODE` | Locate node — path, parents, scope. |
| `tg find PATTERN` | Search nodes by name/property substring. |

**CRUD (8)**

| Command | Purpose |
|---|---|
| `tg add NODE` | Create a node. |
| `tg get NODE` | Read a node's fields. |
| `tg update NODE` | Update node properties. |
| `tg delete NODE` | Delete a node (and its contained subtree per CORE rules). |
| `tg mv SRC DST` | Rename / move a node. |
| `tg link A B --as REL` | Create edge `A --[REL]→ B`. |
| `tg unlink A B` | Delete edge(s) between `A` and `B`. |
| `tg dim NODE [--set K=V]` | Show or set a node's `dimension` property. |

**Special (4)**

| Command | Purpose |
|---|---|
| `tg compliance [PATH]` | Dark Code compliance scan — rules C1–C7. Exit non-zero if violations. |
| `tg trl FILE` | TRL compiler — compile TRL source files to TRUG graphs, or lint in-document TRL blocks. |
| `tg export PATH` | Export TRUG to an archive (JSON bundle). |
| `tg import PATH` | Import an archive back into a TRUG. |

### Sub-namespaces (4)

**`tg memory` — TRUG-backed persistent memory store (8 subs)**

| Command | Purpose |
|---|---|
| `tg memory` | Show recent memories (default, no sub). |
| `tg memory remember FILE TEXT [flags]` | Write a memory. Flags: `--type {user\|feedback\|project\|reference}`, `--rule`, `--rationale`, `--tags`, `--session-id`, `--supersede`, `--valid-to`. |
| `tg memory recall FILE QUERY` | Substring search over memory text, rule, tags, type. |
| `tg memory forget FILE ID` | Close/supersede a memory. |
| `tg memory associate FILE FROM_ID TO_ID [--relation REL]` | Create an edge between two memories. |
| `tg memory render FILE OUT.md [--budget BYTES]` | Render memory TRUG to `MEMORY.md`. |
| `tg memory audit FILE` | Integrity check — dead rules, hit tracking, orphans. |
| `tg memory import PATH` | Bulk-import legacy memory formats. |
| `tg memory reconcile FILE [--threshold N]` | Surface near-duplicate memory candidates for merge review. |

**`tg aaa` — AAA protocol (2 subs)**

| Command | Purpose |
|---|---|
| `tg aaa validate PATH` | Validate an `AAA.md` or AAA TRUG against the 9-phase protocol (v2). Exit 1 if any required phase is missing. |
| `tg aaa generate ISSUE` | Scaffold a new AAA TRUG from a GitHub issue. |

**`tg epic` — EPIC sync (1 sub)**

| Command | Purpose |
|---|---|
| `tg epic sync [FILE]` | Pull REPOSITORY metrics from GitHub into an EPIC TRUG (default: `TRUGS_EPIC/project.trug.json`). Updates `last_commit_at`, `last_pr_merged_at`, `open_issues_count` per REPOSITORY node. |

**`tg render` — specialized renderers (4 targets)**

| Command | Purpose |
|---|---|
| `tg render architecture` | `folder.trug.json` → `ARCHITECTURE.md` (default when no target supplied). |
| `tg render agent` | `agent_instructions.trug.json` → `AGENT.md`. |
| `tg render claude` | `agent_instructions.trug.json` → `CLAUDE.md`. |
| `tg render aaa` | AAA TRUG → `AAA.md`. |

## Global options

```
tg --help            Show usage summary.
tg --version         Print version; exit 0.
tg <cmd> --help      Per-command help.
```

## Dispatch semantics

The CLI dispatcher lives at `trugs_tools.cli:main`. It is a flat dispatch table (`_TG_DISPATCH`) keyed by top-level verb, plus dedicated handlers for sub-namespaces (`_dispatch_memory`, `_dispatch_aaa`, `_dispatch_epic`, `_dispatch_render`).

Legacy handler functions from the pre-1.0 flat multi-binary layout (e.g., `folder_check_command`, `tinit_command`) are preserved in `cli.py` and reused as dispatch targets. New callers should always invoke through `tg <verb>` — the `*_command` functions are implementation detail.

### Collision resolution

Pre-1.0, two separate source trees each exposed a `trugs-tget` CLI with different semantics:

- **`TRUGS/tools/tget.py`** — reads a node from any TRUG file (generic)
- **`TRUGS_TOOLS_development/trugs_tools/filesystem/tget.py`** — filesystem-scoped read

Both implementations are bundled in `trugs-tools 1.0.0`. The dispatcher picks the **TRUGS-side generic implementation** for `tg get` because it's battle-tested against the live memory store used by Claude Code skills.

The filesystem-scoped implementation remains importable as `trugs_tools.filesystem.tget` and can be wired as `tg folder get` (scoped sub-namespace) in a future release if the distinction becomes useful.

Same resolution applies to `tupdate`, `tdelete`, `tunlink`, `validate`.

## Internal utilities (not exposed via `tg`)

Maintainer-only scripts live under `src/trugs_tools/internal/` and are invoked directly:

```bash
python -m trugs_tools.internal.build_language_trug
```

`build_language_trug.py` rebuilds `language.trug.json` from `TRUGS/TRUGS_LANGUAGE/SPEC_vocabulary.md` (external dependency on the TRUGS spec repo). Not a public CLI; not tested in CI.

## Error conventions

| Exit | Meaning |
|---|---|
| 0 | Success. |
| 1 | Validation failure, compliance gap, or domain error with diagnostic message on stderr. |
| 2 | Usage error (unknown command, missing required argument). Help text printed to stdout. |

## Migration from pre-1.0 flat CLIs

`trugs-tools 1.0.0` **breaks** the pre-release flat CLI layout. Every legacy `trugs-*` CLI is replaced:

| Pre-1.0 | 1.0.0+ |
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
| `trugs-trl` | `tg trl` |
| `trugs-compliance-check` | `tg compliance` |
| `trugs-validate` | `tg validate` |
| `trugs-tget` | `tg get` |
| `trugs-tupdate` | `tg update` |
| `trugs-tdelete` | `tg delete` |
| `trugs-tunlink` | `tg unlink` |
| `trugs-tadd`, `tls`, `tcd`, `tfind`, `tmove`, `tlink`, `tdim`, `twatch`, `tsync`, `twhere` | `tg add`, `ls`, etc. (where sensible; some dropped as redundant under the new layout) |
| `trugs-aaa-validate` (from Xepayac/TRUGS-AAA) | `tg aaa validate` |
| `trugs-aaa-generate` | `tg aaa generate` |
| `trugs-agent-render` | `tg render agent` |
| `trugs-claude-render` | `tg render claude` |
| `aaa-validate` (bare) | `tg aaa validate` |

Users with shell aliases, scripts, or CI invoking the old names must update — no compatibility shims are shipped.

## See also

- [`GLOSSARY.md`](./GLOSSARY.md) — terminology reference (133 terms)
- [`GUIDE_quickstart.md`](./GUIDE_quickstart.md) — step-by-step walkthrough
- [`REFERENCE_faq.md`](./REFERENCE_faq.md) — frequently asked questions
- [`SPEC_memory.md`](./SPEC_memory.md), [`SPEC_aaa.md`](./SPEC_aaa.md), [`SPEC_epic.md`](./SPEC_epic.md), [`SPEC_trl.md`](./SPEC_trl.md), [`SPEC_compliance.md`](./SPEC_compliance.md) — subsystem specifications
- [`SPEC_validator.md`](./SPEC_validator.md) — CORE 16-rule structural validator
- [`SPEC_generator.md`](./SPEC_generator.md) — example TRUG generator
- [`SPEC_analyzer.md`](./SPEC_analyzer.md) — graph analysis tools
- [`SPEC_filesystem.md`](./SPEC_filesystem.md) — filesystem TRUG operations
