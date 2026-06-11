# Changelog

All notable changes to `trugs-tools` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Release notes accumulating toward the next `trugs-tools` v2.0 PyPI publish. Bundles
AAA #1976 Phase 7 four-repo polish work + cross-repo sub-phase deliverables per the
bundled-release policy (`mem-98505a37`). Cut to a dated `## [2.0.0]` heading at v2.0
release time per the AAA #1976 Phase 7 coordination checkpoint.

## Added

### L2 shared release infrastructure (AAA #2190 SP3)

Repo-wide Tier-1 release-polish infrastructure, owned solely by sub-AAA S2 (#2190)
and consumed by S3 (#2191) / S4 (#2192):

- **`folder.trug.json`** — the repo's self-describing structure TRUG (root + top-level
  documents + `src/trugs_tools` core/subpackage components + tests/examples/reference),
  VALID against TRUGS's own 16-rule CORE validator (`tg validate`) and clean under the
  folder-render check (`tg check`).
- **`LICENSE` + `NOTICE`** — Apache-2.0 + the patent/provenance notice, mirrored from the
  published `trugs-tools` face so dev and public agree.
- **`Makefile`** — single-command `make check` Tier-1 gate (gitleaks / ruff format / ruff
  lint / mypy / pytest / `tg validate`), scoped to the current Tier-1-green set (core +
  filesystem); the scope widens as S3/S4 baselines land and is closed end-to-end in SP5.
- **`ci-proposed/check.yml`** — staged GitHub Actions workflow running `make check`, held
  out of `.github/workflows/` until a maintainer with `workflow` scope activates it.
- **`CHANGELOG.md`** — this file, finalized from the prior `CHANGELOG_TRUGS_2.0_pending.md`
  staging fragment into Keep-a-Changelog format (the `[Unreleased]` section is now the
  accumulator later sub-phases append to).

### `tg derive` CLI verb (AAA #2004 sub-phase 1)

New top-level verb for invoking registered "producer" functions that emit
derived TRUG artifacts from the canonical memory TRUG. Producer pattern is
the load-bearing primitive of AAA #2004: pure functions read the canonical
and emit purpose-shaped derived TRUGs (LLM glance-load, audit-context,
onboarding, debug — each a separate follow-on AAA). The canonical is never
modified.

CLI signature (ADR-004): positional `producer_name` + optional `--out PATH`
+ optional `--canonical PATH`. Matches `tg events tail N` / `tg memory recall
FILE` / `tg navigate verb` convention.

```
tg derive <producer_name>                         # output to <producer_name>.trug.json
tg derive <producer_name> --out PATH              # custom output path
tg derive <producer_name> --canonical CANONICAL   # override canonical path
```

### `trugs_tools.memory.producers` package (AAA #2004 sub-phase 1)

New public package providing:

- `PRODUCERS` — registry dict mapping producer name → pure function.
- `register(name)` — decorator for registering a producer function.
- `derive(producer_name, out_path=None, canonical_path=None)` — orchestration
  entry point (read canonical via `trugs_store.read_trug` → invoke producer →
  write derived via `trugs_store.write_trug`).

Sub-phase 1 ships the scaffolding only; sub-phase 2 will register
`producer_llm_glance_load` (USER-pinned + ELIGIBLE-ranked + ≤200 entries +
SI-prefix-grouped per ADR-003).

### Recall-aware `ranking_signal` + `citation_scan` (AAA #2004 sub-phase 3, Flavor-2)

`ranking_signal` now reflects organic chat-citation recall in addition to edge
recency. Two pieces:

- `trugs_tools.memory.derived_field_updaters.citation_scan(chat_text, close_count)`
  — a **pure** function that scans session chat text for memory-id citations
  (both hash-form `mem-0595983f` and slug-form `mem-drift-as-evidence-epistemics`)
  and returns one `MemoryRecalled` event per distinct cited id. It never writes
  the canonical TRUG. `memory.cultivation.scan_transcript_to_trl(...)` is the
  close-time boundary that appends those events to the TRL; the reorganizer's
  existing `_handle_memory_recalled` then sets `last_recall_close_count` on
  consume — so the AAA #1814 sole-mutator invariant is preserved (not just
  aspirational).
- `compute_ranking_signal_with_recency` (in `memory.reorganizer`) gains a
  **recall term** `(MENTION_WEIGHT / EDGE_WEIGHT) × recency_decay(close_count −
  last_recall_close_count)`, added to the existing edge term. New module
  constants `MENTION_WEIGHT = 1.0` and `EDGE_WEIGHT = 3.0` (INVARIANT
  `EDGE_WEIGHT > MENTION_WEIGHT` — edges outrank citations). When
  `last_recall_close_count` is `None` the recall term is `0.0`, so
  `ranking_signal` degrades **exactly** to the prior edge-only value — zero
  regression for never-cited memories.

The inherited AAA #2001 `edge_update_recognition` interface is satisfied by the
reorganizer's existing `_handle_edge_created` (which already maintains
`last_edge_close_count`); no separate updater is shipped.

### `tg audit vocab` + `tg audit markdown --all-errors` (AAA #2018 SP1+SP2)

De-masked per-class TRL drift measurement. The default `tg audit markdown`
delegates each `<trl>` block to the full parser, which raises on the **first**
error per block and stops — so a grammar/syntax error on an early statement
masks any out-of-vocabulary word on a later one. Two new opt-in surfaces lift
that masking, per error class:

- **`tg audit vocab PATH [--format text|json] [--language PATH]`** — a
  position-independent vocabulary scanner (`trugs_tools.audit.vocab_scan`). It
  tokenizes each block and runs `classify()` on every `WORD` token, collecting
  **every** out-of-vocabulary token regardless of the block's syntactic or
  grammatical validity. **No parser change** — reuses existing
  `trugs_tools.trl` primitives. A tokenize-level syntax error (bad char /
  unterminated string) triggers line-by-line recovery so it cannot mask misses
  on other lines (flagged per block via `tokenize_recovered`).

- **`tg audit markdown --all-errors`** — error-recovery reporting backed by the
  new `trl.collect_errors(src, lang)`. On a parse error it records the error
  (tagged `TRLVocabularyError` / `TRLGrammarError` / `TRLSyntaxError`), resyncs
  past the next `.` terminator (panic-mode), and continues — reporting **every**
  statement-level error per block instead of just the first. JSON totals carry
  a `per_class_count`.

`trl.collect_errors` + `trl.ParseError` are **additive**: `parse()` itself is
unchanged and still raises on the first error (the contract `tg validate`,
`compile`, and default `tg audit markdown` depend on — INVARIANT
`default_parse SHALL_NOT CHANGE`, regression-covered). Residual
*within-statement* multi-class masking (one statement carrying both a grammar
and a vocab error) is an accepted limitation, fully covered for vocabulary by
the position-independent `tg audit vocab` pass.

### `directive` memory_type + `tg memory migrate-directive` (AAA #2033 SP1)

New `directive` memory_type for HITM-authored standing rules — separating them
from emergent `meta` centroids so `meta` again means exactly one thing (a
centroid over ≥2 constituents). `directive` inherits the above-BASE, KILO-floored,
non-decaying placement of the old `--type user`→`meta` path (AAA #1926 ADR-003)
but carries **no** centroid obligation, so the `meta_under_two_constituents`
validator rule no longer fires on a zero-constituent authored rule.

- **`--type user` is now an input alias for `directive`+KILO** at *both* ingest
  surfaces — the `tg memory remember` argparse alias AND the live `MemoryWritten`
  event path (`_handle_memory_written`, the AAA #1870 `/remember` path). No raw
  `user`-typed node is ever persisted. The public `--type user` CLI surface is
  unchanged.
- **Reorganizer** elevation gains a `directive` arm: `level = max(computed,
  floor_level OR KILO)` — above-BASE, MIN-not-freeze (edge aggregation can still
  push it higher).
- **Validator** repurposes the legacy user-type floor → `directive_type_below_floor`
  (metric_level ≥ KILO); `_check_meta_constituents` stays meta-only (auto-exempts
  `directive`).
- **`tg memory migrate-directive [--file PATH] [--reverse] [--dry-run]`** — new
  rule-scoped migration converting authored metas (`type=meta` AND
  `floor_level=KILO` AND `constituent_count < 2`) → `directive`, keyed on a
  distinct `_migration_2033_original_type` marker for byte-for-byte reversibility.
  Metas with ≥2 constituents (real centroids) are never touched. The AAA #1926
  `migrate-elevation` `user→meta` transform is redirected to `user→directive` so
  no legacy/reverse path re-mints a `meta` from a `user` input.

Additive + backward-compatible: pre-migration stores still validate under the new
`tg` (old `meta` nodes are untouched; the migration is opt-in and reversible).
