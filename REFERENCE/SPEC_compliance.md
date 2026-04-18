# SPEC: `tg compliance` — Dark Code compliance check

**Version:** 1.0.0
**Top-level command:** `tg compliance`
**Python module:** `trugs_tools.compliance_check`

## Purpose

Mechanical audit of a repository against the **Dark Code standard**. The standard demands a four-corner correspondence for every piece of code:

```
        TRUG graph
       ↗          ↘
  source           TRUG/L
  code   ◀─────────▶ inline comments
       ↘          ↗
         annotated tests
```

"Dark Code" is code where any edge of this square is broken. `tg compliance` mechanically verifies every edge.

## Command

```
tg compliance [PATH]
```

`PATH` defaults to cwd. Walks the tree, audits every `.py` source file, every test file, and every `.trug.json` file. Emits per-violation diagnostics and a final percentage.

## Rules

Seven check rules, C1 through C7:

| Rule | What it verifies |
|---|---|
| **C1** | Every public function / class has a function-level TRUG/L comment that parses via `tg trl --validate`. |
| **C2** | Every public function has a corresponding node in the folder's TRUG. |
| **C3** | Every TRUG node with a `trl` property parses via `tg trl --validate`. |
| **C4** | Every test function has an `AGENT SHALL VALIDATE ...` TRL comment that parses. Prefix is strict — other TRL sentences (e.g., `AGENT claude SHALL DEFINE`) fail C4 on tests. |
| **C5** | Every SPEC / FUNCTION / CLASS / STAGE node has ≥1 inbound `VALIDATES` edge from a TEST node. |
| **C6** | Every declared `invariant_*` property has ≥1 assertion in code AND ≥1 test asserting the invariant. |
| **C7** | Every `.trug.json` file passes `tg check` (delegated — C7 is a cross-check to `tg check`). |

## Exit codes

| Exit | Meaning |
|---|---|
| 0 | Compliance = 100.0% AND zero violations. |
| 1 | Any violation present (< 100%). Diagnostics on stderr. |
| 2 | Usage error. |

## Output

### Default (text mode)

```
  C1  src/trugs_tools/foo.py:42 (bar)  public function 'bar' has no TRUG/L comment
  C4  tests/test_foo.py:88 (test_bar)  test function 'test_bar' comment must start with 'AGENT SHALL VALIDATE'
  ...

  Files checked:       42
  Functions checked:   318
  Tests checked:       1930
  TRUG nodes checked:  7
  TRUG files checked:  1
  Violations:          0

  Compliance: 100.0%
```

### JSON mode

```
tg compliance . --format json
```

```json
{
  "compliance_percentage": 100.0,
  "files_checked": 42,
  "functions_checked": 318,
  "tests_checked": 1930,
  "violations": [],
  "violations_by_rule": {"C1": 0, "C2": 0, "C3": 0, "C4": 0, "C5": 0, "C6": 0, "C7": 0}
}
```

## Flags

| Flag | Purpose |
|---|---|
| `--format {text,json}` | Output format (default: `text`). |
| `--strict` | Treat warnings as errors; exit 1 on any finding below 100%. |
| `--quiet` | Summary only; suppress per-violation diagnostics. |
| `--rule RULE` | Run only specified rule (e.g., `--rule C4`). |
| `--exclude PATTERN` | Skip files matching glob (may be repeated). |
| `--baseline FILE` | Write current violations to `FILE`; subsequent runs only report new ones (used by CI to prevent regressions). |

## C4 strictness — the one rule with a prefix requirement

C4 is the only rule that enforces a specific TRL prefix. Valid:

```python
# AGENT SHALL VALIDATE PROCESS test_foo.
def test_foo():
    ...
```

Invalid (fails C4 even though it's valid TRL):

```python
# AGENT claude SHALL DEFINE FUNCTION test_foo.
def test_foo():
    ...
```

Why: every test must declare, in human-readable form, **what it validates**. `AGENT SHALL VALIDATE` is the contract.

## C1 leniency — any valid TRL

For public functions and classes (C1), any parseable TRL sentence works:

```python
# AGENT claude SHALL DEFINE FUNCTION helper.
# AGENT claude SHALL DEFINE RECORD config AS RECORD class.
# PROCESS loader SHALL READ FILE THEN RETURN RECORD data.
```

All three pass C1. The compliance_check does not prescribe prefixes for C1; it requires only that the comment block parse as TRL.

## CI integration

Canonical GitHub Actions workflow:

```yaml
- name: Dark Code compliance gate
  run: |
    pip install trugs-tools
    tg compliance . --strict
```

Hard gates (per `principle_dogfood_own_system` in the TRUGS-DEVELOPMENT EPIC):

- No PR in any TRUGS-LLC repo may decrease `tg compliance` %.
- No version bump (pyproject version) without `tg compliance` = 100%.
- No Xepayac → TRUGS-LLC repo promotion without `tg compliance` = 100%.

## Bulk-annotation pattern (for bringing a repo up to compliance from zero)

See `TRUGS-DEVELOPMENT` memory `mem-ed5cc5c7` for the validated pattern:

1. Write a regex-driven annotator (~30 min to author) that scans `.py` files and inserts minimal TRL comments on every unannotated public function / class / test function.
2. Use `AGENT SHALL VALIDATE PROCESS <name>.` for C4 (strict prefix).
3. Use `AGENT claude SHALL DEFINE FUNCTION <name>.` for C1 (any parseable).
4. Track triple-quote state to avoid corrupting string-literal meta-tests (see `mem-f5788d84`).
5. Hand-fix the last ~0.1% — typically stale non-TRL comments preceding functions that invalidate the whole comment block.

This gets a migrated codebase from 0% → ~99.9% in ~30 minutes; the final 0.1% is manual.

## See also

- [`SPEC_cli.md`](./SPEC_cli.md) — full `tg` CLI surface
- [`SPEC_trl.md`](./SPEC_trl.md) — the TRL compiler that `tg compliance` invokes for C1/C3/C4 parse checks
- TRUGS-LLC/TRUGS/REFERENCE/STANDARD_dark_code_compliance.md — normative standard (this spec is the toolchain side)
- TRUGS-LLC/TRUGS/REFERENCE/PAPER_dark_code.md — the WHY paper
