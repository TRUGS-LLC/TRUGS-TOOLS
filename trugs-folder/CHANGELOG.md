# Changelog

All notable changes to `trugs-folder` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [2.0.0] — 2026-06-12

First standalone release of the cartography package (versions are in
lockstep with `trugs-tools` 2.0).

### Lineage

`trugs-folder` descends from the folder-cartography half of **trugs-tools 1.0.0**
(PyPI, 2026-04-18), where these verbs lived under the unified `tg` binary. The
TRUGS 2.0 commons cleave (AAA #2373) split the cartography tier onto its own
wheel with its own binary, `trug-a-folder`. The v1 → 2.0 verb migration table
is in the [trugs-tools CHANGELOG](https://github.com/TRUGS-LLC/TRUGS-TOOLS/blob/main/CHANGELOG.md).

### Added

- The `trug-a-folder` binary: 14 cartography verbs (init / check / sync /
  render / info / ls / where / find / add / mv / link / dim / export / import),
  each with examples and documented exit codes in `--help`.
- Folder governance checking (`check`): node types and metric levels validated
  against the canonical vocabulary; bidirectional contains-edge integrity.
- `ARCHITECTURE.md` rendering from `folder.trug.json` (`render architecture`).
- Package-owned test suite (`tests/`), relocated from the repo root.

### Fixed

- `init --scan` output now passes its own `check`: scanned nodes carry
  governance-valid types (code → `COMPONENT`, prose/structured-data →
  `DOCUMENT`) and matching metric levels (#56), and contains-edges are
  emitted bidirectionally (#53).
