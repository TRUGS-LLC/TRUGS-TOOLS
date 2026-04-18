# SPEC: `tg aaa` — AAA protocol tooling

**Version:** 1.0.0
**Sub-namespace:** `tg aaa <sub>`
**Python module:** `trugs_tools.aaa_validator` + `trugs_tools.aaa_generator`

## Purpose

Validate and generate **AAA (Autonomous Agentic Audit) protocol** artifacts. AAA is the 9-phase development lifecycle enforced across the TRUGS-LLC portfolio: VISION → FEASIBILITY → SPECIFICATIONS → ARCHITECTURE → VALIDATION (HITM gate) → CODING → TESTING → AUDIT (HITM gate) → DEPLOYMENT.

## Commands

### `tg aaa validate`

```
tg aaa validate PATH
```

Validate an `AAA.md` file OR an AAA TRUG (`.trug.json` with AAA branch vocabulary) against the 9-phase protocol.

Checks performed:

1. **All 9 required phases present** — `VISION`, `FEASIBILITY`, `SPECIFICATIONS`, `ARCHITECTURE`, `VALIDATION`, `CODING`, `TESTING`, `AUDIT`, `DEPLOYMENT`. Missing any one → fail.
2. **ARCHITECTURE section has content** — either a System Design subsection (component maps, dependencies, ADRs) or an Issue TRUG code block with `nodes` and `edges`.
3. **Legacy 7-phase acceptance** — files using the pre-v2 sequence (VISION → FEASIBILITY → SPECIFICATIONS → ARCHITECTURE → CODING → TESTING → DEPLOYMENT) are accepted during the transition period with a deprecation warning.
4. **If input is a TRUG** — validates against `aaa` branch vocabulary: `AAA`, `PHASE`, `TASK`, `AUDIT`, `RISK`, `ADR`, `DEPENDENCY`, `RESEARCH_SOURCE`, `QUALITY_GATE` node types; `precedes`, `depends_on`, `blocked_by`, `mitigates`, `validates`, `tracks`, `cites`, `decides` edge relations.

Exit 0 if valid; exit 1 with diagnostic on stderr if invalid.

### `tg aaa generate`

```
tg aaa generate ISSUE
```

Scaffold a new AAA TRUG from a GitHub issue. `ISSUE` is a local issue number or a full URL.

Output: `AAA_<ISSUE>_<slug>.trug.json` in the current directory, pre-populated with the 9 phase skeletons, the issue title as the VISION, and issue metadata (author, created date, labels) as node properties.

Then render the TRUG to Markdown:

```
tg render aaa AAA_<ISSUE>_<slug>.trug.json
```

Produces `AAA.md` for human review.

## AAA TRUG schema summary

The `aaa` branch vocabulary defines:

**Node types (9)**

| Type | Purpose |
|---|---|
| `AAA` | Root — one per AAA TRUG. Contains the issue and all phases. |
| `PHASE` | One of the 9 phases. Properties: `phase_name`, `phase_number`, `hitm_gate`, `status`. |
| `TASK` | Unit of work within a phase. Leaf-level. |
| `AUDIT` | Cyclic audit session within the AUDIT phase. Multiple audits per AAA. |
| `RISK` | Identified risk. Properties: `severity`, `mitigation`. |
| `ADR` | Architectural Decision Record. |
| `DEPENDENCY` | External dependency (other issue, PR, external service). |
| `RESEARCH_SOURCE` | Citation or reference material. |
| `QUALITY_GATE` | HITM gate (VALIDATION after phase 4, AUDIT after phase 8). |

**Edge relations (8)**

| Relation | Purpose |
|---|---|
| `precedes` | Ordering between phases or tasks. |
| `depends_on` | Hard dependency — cannot start until target resolved. |
| `blocked_by` | Transient block. |
| `mitigates` | Task mitigates a risk. |
| `validates` | Test validates a task / spec. |
| `tracks` | AAA tracks an issue. |
| `cites` | References a research source. |
| `decides` | ADR decides a specific choice. |

## Canonical example

See the TRUGS-AGENT repo:

```
TRUGS-LLC/TRUGS-AGENT/AAA/
├── AGENT.md                                    pedagogical overview
├── GUIDE_aaa_workflow_for_llm_agents.md        deep-dive (21 KB)
├── AAA_REFERENCE_for_LLM.trug.json             canonical protocol as TRUG (16 KB)
├── EXAMPLE_canonical.trug.json                 full 9-phase example (14 KB)
└── EXAMPLE_email_mcp.md                        applied example
```

For bundled test fixture: `tests/fixtures/aaa_canonical_example.trug.json`.

## The two HITM gates

AAA enforces human-in-the-middle approval at exactly two points:

1. **VALIDATION (after phase 4)** — human approves the plan before coding begins. If the agent enters CODING without a validated plan, `tg aaa validate` flags the missing `QUALITY_GATE validation` node.
2. **AUDIT (after phase 8)** — human approves audit findings and triggers DEPLOYMENT. Cyclic audits loop here until no critical/high findings remain.

## Migration note

Pre-1.0, this validator shipped from `Xepayac/TRUGS-AAA` as `aaa-validate`. That repo is archived; content migrated to `trugs-tools` (code → `src/trugs_tools/aaa_validator.py`) and `trugs-agent/AAA/` (docs → GUIDE, canonical TRUG, examples). See EPIC #1576 G1 for migration history.

## See also

- [`SPEC_cli.md`](./SPEC_cli.md) — full `tg` CLI surface
- [`SPEC_validator.md`](./SPEC_validator.md) — CORE structural validator
- TRUGS-LLC/TRUGS-AGENT/AAA/ — pedagogical AAA materials
