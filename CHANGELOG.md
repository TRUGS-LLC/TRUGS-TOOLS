# Changelog

All notable changes to `trugs-tools` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- `LICENSE` and `trugs-folder/LICENSE` are the official Apache License 2.0 text; `NOTICE` and
  `trugs-folder/NOTICE` carry the attribution only, their patent paragraphs and the provenance section removed;
  both READMEs gain a Scope section.

## [2.2.0] — 2026-08-11

**`validate` now rejects graphs it previously accepted.** If you validate TRUG files in CI, expect
`trug validate` to exit `1` where it exited `0`. This is a deliberate tightening, not a regression:
the validator was certifying broken hierarchies as `VALID`.

### Changed — `validate` rejects broken hierarchies

`rule_3` (hierarchy consistency) carried two skip-guards. A reference naming a node that does not
exist caused the consistency check to be *skipped* rather than failed, so the graph came back `VALID`
and the command exited `0`. There was separately no acyclicity check anywhere, so a node could be its
own parent and still validate. `rule_2` has always erred on a dangling *edge* reference; hierarchy is
now held to the same standard.

| Code | Rejects |
|---|---|
| `DANGLING_PARENT_ID` | `parent_id` names a node that does not exist — including `parent_id: ""` |
| `DANGLING_CONTAINS` | a `contains[]` entry names a node that does not exist |
| `HIERARCHY_CYCLE` | the parent chain closes on itself, including a node parented to itself |
| `INVALID_FIELD_TYPE` | a `contains[]` entry that is not a string |

The rule *count* is unchanged: these are new error codes inside rule 3, not new rules. The CORE
ruleset remains 16 — 9 structural, always, plus 7 compositional when the graph declares
`core_v2.0.0`.

The cross-folder `FOLDER:node_id` reference form remains edges-only. It is rejected in `parent_id`
and `contains[]`, deliberately and asymmetrically with `rule_2`: a parent must live in the same
graph.

### Fixed — a crash that read as a clean run

A `contains[]` entry that was a dict or a list raised an uncaught `TypeError` from the membership
test. `validate_file` catches only JSON and OS errors, so `trug validate --all` aborted mid-corpus
and left every remaining file unvalidated — indistinguishable from success to a gate that reads only
the exit code. Such entries now report `INVALID_FIELD_TYPE`.

`HIERARCHY_CYCLE` reporting is order-independent (an order-only reshuffle of the same graph produces
the same message) and bounded (a large ring reports 12 members and its true length, rather than
rendering the whole ring).

### Fixed — the commands that write graphs no longer produce ones `validate` rejects

Tightening the validator exposed five defects in the verbs that write hierarchies, all of the same
shape: the bidirectional link was maintained on one side only. Each reported success while emitting a
graph the same release rejects.

- **`trug delete`** stripped deleted ids from every surviving `contains[]` and never repaired the
  orphaned children's `parent_id`. Orphans are now adopted by their nearest surviving ancestor —
  walking up through the whole deleted set — or become roots when none survives. Reported in the
  output and in `--dry-run`.
- **`trug update --parent`** had neither an existence check nor an ancestor check: a nonexistent
  parent printed a warning and wrote anyway, and a node could be made its own parent silently. Both
  are now refused with exit `1` and nothing written. Validation happens before any mutation.
- **`trug-a-folder mv --parent`** checked that the new parent exists, not that it is a
  non-descendant. Moving a node under its own child now refuses.
- **`trug-a-folder sync --prune-after N`** repaired only the root `FOLDER` node's `contains[]` when
  pruning, orphaning a pruned parent's children. Every surviving `contains[]` is now repaired and
  orphans re-parented by the same rule as `delete`.

Re-parenting maintains all three halves of containment — `parent_id`, the parent's `contains[]`, and
the containment edge. `trug update --parent` previously moved the first two and left the edge
pointing at the parent the node had left. A graph that expressed containment only through
`contains[]` acquires no edge: these commands repair the links they move and do not author structure
that was never written.

Correction, 2026-10-16: The containment-edge update described above applies to
`trug update --parent`. `trug-a-folder mv --parent` updates `parent_id` and the
parents' `contains[]` arrays but leaves edges unchanged, including any existing
containment edge to the old parent.

### Fixed — packaging

`LICENSE`, `NOTICE` and `README.md` are back in the sdist and the wheel, and the PyPI project page
renders again. They had been absent since 2.1.1 — see that entry.

### Fixed — documentation

`AGENT.md` described `trug validate` as checking "the 12 structural rules". The count has been 16
since 2.0; the README was corrected in 2.1.2 and this file was missed. The repo's own
`folder.trug.json` carried the same stale claim in two node descriptions.

---

## [2.1.2] — 2026-07-27

The public release of the content-identity digest — already published as 2.1.1 two days earlier, from
the staging mirror, without a corresponding public commit. See 2.1.1 for the feature. This version
exists to restore the promote-then-publish ordering; publishing ahead of promotion had wedged the
release-parity gate.

### Fixed

Stale specification labels shipping in 2.1.1, corrected across the package: "TRUGS v1.0" → "TRUGS
v2.0" in the validator and in eight schema titles and descriptions; the TRL vocabulary count 211 →
233; and the README's "12 structural rules" → "16 CORE rules".

### Known defect

The packaging regression introduced in 2.1.1 (below) is present in this release too, and is fixed in
2.2.0.

## [2.1.1] — 2026-07-25

**Published from the staging mirror with no corresponding public release commit.** No commit in this
repository has ever carried version `2.1.1`; it is on PyPI and was promoted here as 2.1.2. Recorded
rather than omitted, because a version gap with no entry is exactly what sends a reader looking for a
yanked release.

### Added

`trugs_tools.digest` — a stdlib-only RFC-8785/JCS canonical encoder and a layered content-addressed
tree digest producing a self-describing `tci1-sha256-<hex>` identifier. Three layers: `L0`
`structural_identity` (a Merkle fold over `contains`, order-insensitive, plus the sorted de-duplicated
edge set), `L1` `artifact_identity` (the default), and `L2` `dimension_identity` (per-dimension). The
reserved `_derived` namespace is excluded so volatile fields never churn identity; content references
are used literally and never resolved, keeping the function pure; non-finite numbers and integers
outside the I-JSON safe range are rejected rather than coerced.

It is a **library API only** — no CLI verb, and not re-exported from the package root. Import it as
`from trugs_tools.digest import digest`.

Adds no runtime dependency. `jcs` and `rfc8785` were added to the `test` extra as byte-oracles.

### Known defect — fixed in 2.2.0

`LICENSE`, `NOTICE` and `README.md` were dropped from the sdist and the wheel, and the PyPI long
description became empty, so the project page has rendered blank from this release onward. The cause
was the move of the publish source to the staging tree, which does not carry those files while
`pyproject.toml` continued to declare them; the build emitted a single warning and exited `0`. Both
2.1.1 and 2.1.2 are affected and neither has been yanked.

## [2.1.0] — 2026-07-18

Released together with `trugs-folder` 2.1.0.

### Changed — breaking

- **`trl compile` returns a complete graph.** It previously returned a bare `{nodes, edges}` fragment;
  it now returns a full TRUG that `trug validate` accepts — CORE envelope, every node carrying its
  seven CORE fields, a synthetic `PROJECT` root containing the compiled nodes, and a
  `capabilities.vocabularies: ["core_v2.0.0"]` declaration.
- **The compositional tier is armed by `core_v2.0.0`.** Rules 10–16 were previously armed only by
  `core_v1.0.0`, so a graph declaring the current vocabulary received the nine structural rules and
  nothing else.
- **`core_v1.0.0` is now rejected** with `RETIRED_VOCABULARY`, short-circuiting the compositional tier.
  Structural verdicts still stand.
- **`trug-a-folder sync` no longer prunes by default.** `--prune-after` moved from `7` to `0`; nodes
  are removed only when pruning is explicitly requested.

### Added

`trl.compile()` accepts a `name` argument setting the graph name. The CLI passes the input file's
stem; input from stdin gets the deterministic default `trug_graph`.

### Fixed

- A malformed `capabilities.vocabularies` — not a list, or a list containing non-strings — now fails
  with `INVALID_FIELD_TYPE` instead of degrading silently to "no declaration", which had let a
  string-form declaration of the retired vocabulary pass unnoticed.
- Rule 11 no longer false-positives on modal edges (`SHALL`, `SHALL_NOT`, `MAY`); modal actor-to-
  operation bindings are rule 14's jurisdiction.
- `trl validate` accepts `PROJECT` as a structural node type, so graphs carrying the new completion
  root pass the noun-vocabulary check.
- CLI verb dispatch inspects the handler's signature instead of calling it and catching `TypeError`,
  so a `TypeError` raised *inside* a handler surfaces as that handler's bug rather than being misread
  as a signature mismatch and silently re-run.
- `trug-a-folder check` no longer rejects edge relations that `trug-a-folder link` itself writes.

### Removed

`rules.py` shrank from 600 lines to 91, dropping a second, drift-prone copy of rules 1–9 and
`validate_required_root_fields`. No user-visible effect: nothing called them. The module now holds
only the two verdict-neutral warning checks it was actually wired for.

## [2.0.0] — 2026-06-12

The TRUGS 2.0 commons release. Bundles AAA (private reference removed) Phase 7 four-repo polish work +
cross-repo sub-phase deliverables per the bundled-release policy (`mem-98505a37`).
Published to PyPI together with `trugs-folder` 2.0.0 and `trugs-store` 2.0.0 — the
three-package Apache commons kit (dependency order `trugs-store` < `trugs-tools` <
`trugs-folder`).

## The 2.0 boundary statement

`trugs-tools` 1.0.0 was the last Apache release containing the memory, AAA, and
epic system family under the unified `tg` binary. As of 2.0, the Apache commons
is exactly two packages:

- **`trugs-tools`** — the language CLI, `trug` (this package);
- **`trugs-folder`** — folder cartography, `trug-a-folder`.

Correction, 2026-10-16: The package count above omitted `trugs-store` (graph
persistence). The Apache commons kit has three packages: `trugs-tools`,
`trugs-folder`, and `trugs-store`, as stated in the release introduction.

Correction, 2026-10-16: The NOTICE accompanying the 2.0.0 release contained a
patent paragraph, removed on 2026-10-16. NOTICE now carries Apache attribution
only; see the [README Scope section](./README.md#scope) for the current scope note.

`trugs-tools` 1.0.0 remains available on PyPI unchanged; existing v1 graph
files are data and are untouched by any of this.

### Migrating from v1 (`tg`) to 2.0

| v1 verb (`tg …`) | 2.0 home |
|---|---|
| `tg validate` | `trug validate` |
| `tg trl compile/decompile/validate` | `trug trl compile/decompile/validate` |
| `tg get` / `tg update` / `tg delete` / `tg unlink` | `trug get` / `trug update` / `trug delete` / `trug unlink` |
| `tg compliance` | `trug compliance` |
| `tg init` / `check` / `sync` / `render` / `info` / `ls` / `where` / `find` / `add` / `mv` / `link` / `dim` / `export` / `import` | `trug-a-folder <same verb>` (package `trugs-folder`) |
| `tg memory …` / `tg aaa …` / `tg epic …` | not in the 2.0 Apache packages — remain available in `trugs-tools` 1.0.0; see the boundary statement above |

## Added

### L2 shared release infrastructure (AAA (private reference removed) SP3)

Repo-wide Tier-1 release-polish infrastructure, owned solely by sub-AAA S2 ((private reference removed))
and consumed by S3 ((private reference removed)) / S4 ((private reference removed)):

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

Correction, 2026-10-16: The infrastructure list above describes historical staging.
The shipped tree has no root `tests/`, `examples/`, `REFERENCE/`, or
`ci-proposed/check.yml`. Its `make check` runs `pytest trugs-folder/tests/` and
`trug validate folder.trug.json`; it does not run the other gates listed above.
The packaged NOTICE now contains Apache attribution only.

### `tg derive` CLI verb (AAA (private reference removed) sub-phase 1)

New top-level verb for invoking registered "producer" functions that emit
derived TRUG artifacts from the canonical memory TRUG. Producer pattern is
the load-bearing primitive of AAA (private reference removed): pure functions read the canonical
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

Correction, 2026-10-16: The `tg derive` section above records historical system-tier staging.
This public language package does not ship that verb.

### `trugs_tools.memory.producers` package (AAA (private reference removed) sub-phase 1)

New public package providing:

- `PRODUCERS` — registry dict mapping producer name → pure function.
- `register(name)` — decorator for registering a producer function.
- `derive(producer_name, out_path=None, canonical_path=None)` — orchestration
  entry point (read canonical via `trugs_store.read_trug` → invoke producer →
  write derived via `trugs_store.write_trug`).

Sub-phase 1 ships the scaffolding only; sub-phase 2 will register
`producer_llm_glance_load` (USER-pinned + ELIGIBLE-ranked + ≤200 entries +
SI-prefix-grouped per ADR-003).

Correction, 2026-10-16: The `trugs_tools.memory.producers` section above records historical
system-tier staging. This public language package has no `trugs_tools.memory`
package and does not ship those producer APIs.

### Recall-aware `ranking_signal` + `citation_scan` (AAA (private reference removed) sub-phase 3, Flavor-2)

`ranking_signal` now reflects organic chat-citation recall in addition to edge
recency. Two pieces:

- `trugs_tools.memory.derived_field_updaters.citation_scan(chat_text, close_count)`
  — a **pure** function that scans session chat text for memory-id citations
  (both hash-form `mem-0595983f` and slug-form `mem-drift-as-evidence-epistemics`)
  and returns one `MemoryRecalled` event per distinct cited id. It never writes
  the canonical TRUG. `memory.cultivation.scan_transcript_to_trl(...)` is the
  close-time boundary that appends those events to the TRL; the reorganizer's
  existing `_handle_memory_recalled` then sets `last_recall_close_count` on
  consume — so the AAA (private reference removed) sole-mutator invariant is preserved (not just
  aspirational).
- `compute_ranking_signal_with_recency` (in `memory.reorganizer`) gains a
  **recall term** `(MENTION_WEIGHT / EDGE_WEIGHT) × recency_decay(close_count −
  last_recall_close_count)`, added to the existing edge term. New module
  constants `MENTION_WEIGHT = 1.0` and `EDGE_WEIGHT = 3.0` (INVARIANT
  `EDGE_WEIGHT > MENTION_WEIGHT` — edges outrank citations). When
  `last_recall_close_count` is `None` the recall term is `0.0`, so
  `ranking_signal` degrades **exactly** to the prior edge-only value — zero
  regression for never-cited memories.

The inherited AAA (private reference removed) `edge_update_recognition` interface is satisfied by the
reorganizer's existing `_handle_edge_created` (which already maintains
`last_edge_close_count`); no separate updater is shipped.

Correction, 2026-10-16: The recall-aware ranking and citation-scan section above records historical
system-tier staging. This public language package does not ship those memory
APIs or the reorganizer.

### `tg audit vocab` + `tg audit markdown --all-errors` (AAA (private reference removed) SP1+SP2)

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

### `directive` memory_type + `tg memory migrate-directive` (AAA (private reference removed) SP1)

New `directive` memory_type for HITM-authored standing rules — separating them
from emergent `meta` centroids so `meta` again means exactly one thing (a
centroid over ≥2 constituents). `directive` inherits the above-BASE, KILO-floored,
non-decaying placement of the old `--type user`→`meta` path (AAA (private reference removed) ADR-003)
but carries **no** centroid obligation, so the `meta_under_two_constituents`
validator rule no longer fires on a zero-constituent authored rule.

- **`--type user` is now an input alias for `directive`+KILO** at *both* ingest
  surfaces — the `tg memory remember` argparse alias AND the live `MemoryWritten`
  event path (`_handle_memory_written`, the AAA (private reference removed) `/remember` path). No raw
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
  Metas with ≥2 constituents (real centroids) are never touched. The AAA (private reference removed)
  `migrate-elevation` `user→meta` transform is redirected to `user→directive` so
  no legacy/reverse path re-mints a `meta` from a `user` input.

Additive + backward-compatible: pre-migration stores still validate under the new
`tg` (old `meta` nodes are untouched; the migration is opt-in and reversible).

Correction, 2026-10-16: The directive-memory section above records historical
system-tier staging. This public language package does not ship memory, the
reorganizer, or `tg memory migrate-directive`.
