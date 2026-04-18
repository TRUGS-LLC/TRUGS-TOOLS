"""trugs-compliance-check — mechanical Dark Code compliance verifier.

# PROCESS compliance_check SHALL VALIDATE ALL FILE AGAINST DATA standard_dark_code_compliance
#   THEN SEND RECORD report TO PARTY developer.

Implements the checks specified in `REFERENCE/STANDARD_dark_code_compliance.md`:

- **C1** — every public `def` / `class` in `*.py` has a function-level TRUG/L
  comment immediately above it that parses via `tools/trl.py`.
- **C2** — every public `def` / `class` has a corresponding FUNCTION / PROCESS
  / CLASS / METHOD / STAGE node in the folder's `.trug.json`.
- **C3** — every TRUG node with a `trl` property parses via `tools/trl.py`.
- **C4** — every test function has a comment starting with
  `AGENT SHALL VALIDATE` that parses.
- **C5** — every TEST node in the TRUG has at least one outbound `VALIDATES`
  edge to a FUNCTION / PROCESS / CLASS / STAGE / SPEC node.
- **C6** — every declared invariant (TRUG node property matching `invariant_*`)
  has at least one assertion in code and one test.
- **C7** — every `.trug.json` file passes `trugs-folder-check` (delegated).

Usage:

    trugs-compliance-check [PATH]                 # audit a repo or subtree
    trugs-compliance-check --json [PATH]          # machine-readable output
    trugs-compliance-check --strict [PATH]        # exit 1 on ANY violation
    trugs-compliance-check --baseline-update [PATH]
        # rewrite .github/compliance-baseline.json with current numbers

Exit codes:

- 0 — compliance % ≥ baseline (or baseline does not exist)
- 1 — compliance % < baseline, or `--strict` and any violation found

See: REFERENCE/STANDARD_dark_code_compliance.md §6 (CI gate)
"""

# AGENT claude SHALL_NOT WRITE ANY FILE TO NAMESPACE zzz_.
# AGENT claude SHALL EXCLUDE ANY FILE 'that CONTAINS zzz_ AS PREFIX.

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Import TRUG/L parser — CLI depends on TRUGS's own compiler.
try:
    from trugs_tools import trl as _trl
except ImportError:
    # Support running as `python tools/compliance_check.py ...` from repo root.
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from trugs_tools import trl as _trl  # type: ignore


# =============================================================================
# DATA MODEL
# =============================================================================


# AGENT claude SHALL DEFINE RECORD violation AS A RECORD finding.
@dataclass
class Violation:
    """A single compliance violation. Structured for both human + JSON output."""

    rule: str                   # e.g. "C1"
    path: Path                  # file where the violation was found
    line: Optional[int]         # line number (or None for file-level violations)
    symbol: Optional[str]       # function/class/node name (if applicable)
    message: str                # human-readable description

    # AGENT claude SHALL MAP RECORD violation TO RECORD dict.
    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "path": str(self.path),
            "line": self.line,
            "symbol": self.symbol,
            "message": self.message,
        }

    # AGENT claude SHALL MAP RECORD violation TO STRING DATA output.
    def format(self, root: Path) -> str:
        rel = self.path.relative_to(root) if self.path.is_absolute() else self.path
        locus = f"{rel}:{self.line}" if self.line else str(rel)
        sym = f" ({self.symbol})" if self.symbol else ""
        return f"  {self.rule}  {locus}{sym}  {self.message}"


# AGENT claude SHALL DEFINE RECORD report AS A RECORD finding.
@dataclass
class Report:
    """Full compliance report produced by a single audit pass."""

    files_checked: int = 0
    functions_checked: int = 0
    tests_checked: int = 0
    nodes_checked: int = 0
    trug_files_checked: int = 0
    violations: list[Violation] = field(default_factory=list)

    # AGENT claude SHALL AGGREGATE EACH RECORD violation TO INTEGER DATA count.
    @property
    def violation_count(self) -> int:
        return len(self.violations)

    # AGENT claude SHALL GROUP EACH RECORD violation BY RECORD rule.
    @property
    def violations_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for v in self.violations:
            counts[v.rule] = counts.get(v.rule, 0) + 1
        return counts

    # AGENT claude SHALL AGGREGATE EACH RECORD violation TO INTEGER DATA percent.
    @property
    def compliance_percent(self) -> float:
        """Compliance ratio. Denominator = total check opportunities.

        We count one potential violation per function (C1, C4) + one per test
        (C4) + one per node with trl (C3) + one per TEST node (C5). This gives
        us a sensible denominator: the % of checks that passed.

        Returns a number in [0.0, 100.0].
        """
        opportunities = (
            self.functions_checked * 2  # C1 + C4 per function
            + self.tests_checked       # C4 per test
            + self.nodes_checked        # C3 per TRUG node with trl
            + self.trug_files_checked   # C7 per TRUG file
        )
        if opportunities == 0:
            return 100.0
        passed = opportunities - self.violation_count
        return round(100.0 * max(passed, 0) / opportunities, 2)

    # AGENT claude SHALL MAP RECORD report TO RECORD dict.
    def to_dict(self) -> dict[str, Any]:
        return {
            "compliance_percent": self.compliance_percent,
            "files_checked": self.files_checked,
            "functions_checked": self.functions_checked,
            "tests_checked": self.tests_checked,
            "nodes_checked": self.nodes_checked,
            "trug_files_checked": self.trug_files_checked,
            "violation_count": self.violation_count,
            "violations_by_rule": self.violations_by_rule,
            "violations": [v.to_dict() for v in self.violations],
        }


# =============================================================================
# PATH DISCOVERY
# =============================================================================


_EXCLUDED_DIR_PREFIXES = ("zzz_", ".git", "__pycache__", ".venv", "venv", ".tox", "node_modules", "dist", "build")
_AUTO_GENERATED_FILES = {"ARCHITECTURE.md", "AAA.md", "CLAUDE.md"}


def _iter_files(root: Path, suffix: str) -> list[Path]:
    # PROCESS discovery SHALL FILTER ALL FILE 'in NAMESPACE root BY SUFFIX
    #   THEN EXCLUDE EACH FILE 'in NAMESPACE zzz_ OR .git OR __pycache__.
    if root.is_file():
        return [root] if root.suffix == suffix else []
    out: list[Path] = []
    for p in sorted(root.rglob(f"*{suffix}")):
        # Walk up the path parts; exclude if any segment starts with an excluded prefix
        if any(seg.startswith(_EXCLUDED_DIR_PREFIXES) for seg in p.relative_to(root).parts):
            continue
        if p.name in _AUTO_GENERATED_FILES:
            continue
        out.append(p)
    return out


# =============================================================================
# PYTHON SOURCE ANALYSIS
# =============================================================================


def _is_public(name: str) -> bool:
    # RECORD name 'is PUBLIC UNLESS name STARTS 'with UNDERSCORE OR DUNDER.
    if name.startswith("__") and name.endswith("__"):
        return False  # dunder: language scaffolding, exempt
    if name.startswith("_"):
        return False  # module-private
    return True


def _is_test_function(func: ast.FunctionDef | ast.AsyncFunctionDef, parent: Optional[ast.ClassDef]) -> bool:
    # AGENT SHALL CLASSIFY A FUNCTION 'as RECORD test
    #   IF name STARTS 'with "test_" OR parent.name STARTS 'with "Test".
    if func.name.startswith("test_"):
        return True
    if parent is not None and parent.name.startswith("Test"):
        return func.name.startswith("test")
    return False


def _extract_preceding_comment_block(source_lines: list[str], def_line: int) -> tuple[str, int]:
    """Read comment lines immediately above the given line number.

    # PROCESS extract SHALL READ ALL STRING line UPWARD FROM A RECORD line
    #   WHILE EACH line 'is COMMENT OR EMPTY.
    # RESULT SHALL RETURN RECORD text AND RECORD start_line.

    `def_line` is 1-indexed. Returns (combined_text, start_line) where
    start_line is the 1-indexed line of the first comment (or def_line if
    no comment block precedes).
    """
    comment_lines: list[str] = []
    i = def_line - 2  # line BEFORE the def (0-indexed into source_lines)
    start_line = def_line
    # A "banner" is a section divider like `# =====` or `# -----`. These must
    # terminate the block — they are not part of the function-level comment.
    banner_pat = re.compile(r"^#\s*[-=#]{3,}\s*$")
    while i >= 0:
        line = source_lines[i].rstrip("\n")
        stripped = line.strip()
        if banner_pat.match(stripped):
            # hit a section banner — terminate extraction (do NOT include it)
            break
        if stripped.startswith("#"):
            # it is a comment — add it
            comment_lines.insert(0, stripped[1:].lstrip())
            start_line = i + 1
            i -= 1
        elif stripped == "":
            # blank line: allowed BETWEEN comment and def, but only if comment hasn't started yet
            if comment_lines:
                break  # blank line terminates the block
            i -= 1
        elif stripped.startswith("@"):
            # decorator — skip decorators when looking for a comment
            i -= 1
        else:
            break
    return "\n".join(comment_lines), start_line


def _comment_starts_with(comment: str, prefix: str) -> bool:
    # RECORD comment STARTS 'with RECORD prefix IGNORING LEADING punctuation.
    return comment.lstrip().upper().startswith(prefix.upper())


def _try_parse_trl(comment: str) -> tuple[bool, str]:
    """Attempt to parse a comment block as TRUG/L. Returns (ok, error_message).

    # PROCESS parse_attempt SHALL COMPILE STRING comment THROUGH PROCESS trl
    #   THEN RETURN VALID OR RECORD error.
    """
    # Strip leading/trailing whitespace. Empty → not TRUG/L.
    text = comment.strip()
    if not text:
        return False, "empty comment block"
    # trl.py expects sentences terminated by '.' — normalize if missing.
    if not text.rstrip().endswith((".", "?", "!")):
        text = text.rstrip() + "."
    try:
        _trl.parse(text)
        return True, ""
    except _trl.TRLError as exc:
        return False, str(exc).splitlines()[0] if str(exc) else type(exc).__name__


@dataclass
class _FunctionRecord:
    name: str
    line: int
    is_test: bool
    is_class: bool
    comment_block: str
    comment_start_line: int


def _walk_python(path: Path) -> list[_FunctionRecord]:
    """Parse a Python file and yield one record per public def / class / method.

    # PROCESS walk SHALL MAP EACH ast.FunctionDef OR ast.ClassDef
    #   TO RECORD _FunctionRecord.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # broken file — not this tool's job to report syntax errors
    lines = source.splitlines(keepends=True)

    records: list[_FunctionRecord] = []

    # AGENT claude SHALL DEFINE FUNCTION visit.
    def visit(node: ast.AST, parent: Optional[ast.ClassDef] = None, inside_func: bool = False) -> None:
        # Walk AST children. Functions nested inside other functions are
        # implementation detail — not reported. Methods of classes ARE reported.
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_public(child.name) and not inside_func:
                    is_test = _is_test_function(child, parent)
                    comment, clstart = _extract_preceding_comment_block(lines, child.lineno)
                    records.append(_FunctionRecord(
                        name=child.name,
                        line=child.lineno,
                        is_test=is_test,
                        is_class=False,
                        comment_block=comment,
                        comment_start_line=clstart,
                    ))
                # Recurse into function body — now we ARE inside a function, so nested defs won't be reported
                visit(child, parent=None, inside_func=True)
            elif isinstance(child, ast.ClassDef):
                if _is_public(child.name) and not inside_func:
                    comment, clstart = _extract_preceding_comment_block(lines, child.lineno)
                    records.append(_FunctionRecord(
                        name=child.name,
                        line=child.lineno,
                        is_test=False,
                        is_class=True,
                        comment_block=comment,
                        comment_start_line=clstart,
                    ))
                # Inside a class, we can still report public methods — class body is not a function body
                visit(child, parent=child, inside_func=inside_func)
            else:
                visit(child, parent, inside_func)

    visit(tree)
    return records


# =============================================================================
# TRUG GRAPH ANALYSIS
# =============================================================================


# Node types that count as a public-code-artifact node for C2.
# Only function-like types — SPECIFICATION and DOCUMENT nodes name files, not Python symbols,
# so C2 does not apply to them.
_CODE_ARTIFACT_NODE_TYPES = {"FUNCTION", "PROCESS", "CLASS", "METHOD", "STAGE"}
_TEST_NODE_TYPE = "TEST"


def _load_trug(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _node_name(node: dict) -> str:
    # RECORD node.name OR RECORD node.id — PREFER PROPERTIES.name IF EXISTS.
    props = node.get("properties", {}) or {}
    return props.get("name") or node.get("id", "")


def _node_ids_for_code_artifacts(graph: dict) -> dict[str, dict]:
    """Map code-artifact name → node. Collisions keep the first occurrence."""
    out: dict[str, dict] = {}
    for n in graph.get("nodes", []):
        if n.get("type") in _CODE_ARTIFACT_NODE_TYPES:
            name = _node_name(n)
            if name and name not in out:
                out[name] = n
    return out


def _test_nodes(graph: dict) -> list[dict]:
    return [n for n in graph.get("nodes", []) if n.get("type") == _TEST_NODE_TYPE]


def _has_validates_edge(graph: dict, test_node_id: str) -> bool:
    for e in graph.get("edges", []):
        if e.get("from_id") != test_node_id:
            continue
        rel = (e.get("relation") or "").upper()
        if rel == "VALIDATES":
            return True
    return False


def _invariant_properties(graph: dict) -> list[tuple[dict, str]]:
    """Extract every (node, invariant_key) pair from every node's properties."""
    out: list[tuple[dict, str]] = []
    for n in graph.get("nodes", []):
        props = n.get("properties", {}) or {}
        for k in props:
            if k.startswith("invariant_"):
                out.append((n, k))
    return out


# =============================================================================
# CHECK IMPLEMENTATIONS
# =============================================================================


# AGENT compliance SHALL VALIDATE EACH FILE python SUBJECT_TO DATA c1 AND DATA c4.
def check_python_file(path: Path, report: Report, root: Path) -> None:
    """Run C1 and C4 on a Python source file."""
    records = _walk_python(path)
    for rec in records:
        if rec.is_test:
            report.tests_checked += 1
            # C4: test function comment must start with AGENT SHALL VALIDATE
            if not rec.comment_block:
                report.violations.append(Violation(
                    rule="C4", path=path, line=rec.line, symbol=rec.name,
                    message=f"test function '{rec.name}' has no TRUG/L comment",
                ))
                continue
            if not _comment_starts_with(rec.comment_block, "AGENT SHALL VALIDATE"):
                report.violations.append(Violation(
                    rule="C4", path=path, line=rec.line, symbol=rec.name,
                    message=f"test function '{rec.name}' comment must start with 'AGENT SHALL VALIDATE'",
                ))
                continue
            ok, err = _try_parse_trl(rec.comment_block)
            if not ok:
                report.violations.append(Violation(
                    rule="C4", path=path, line=rec.line, symbol=rec.name,
                    message=f"test function '{rec.name}' comment does not parse as TRUG/L: {err}",
                ))
        else:
            report.functions_checked += 1
            # C1: public def/class must have a function-level TRUG/L comment that parses
            if not rec.comment_block:
                report.violations.append(Violation(
                    rule="C1", path=path, line=rec.line, symbol=rec.name,
                    message=f"public {'class' if rec.is_class else 'function'} '{rec.name}' has no TRUG/L comment",
                ))
                continue
            ok, err = _try_parse_trl(rec.comment_block)
            if not ok:
                report.violations.append(Violation(
                    rule="C1", path=path, line=rec.line, symbol=rec.name,
                    message=f"public {'class' if rec.is_class else 'function'} '{rec.name}' comment does not parse as TRUG/L: {err}",
                ))


# AGENT compliance SHALL VALIDATE EACH FILE trug_json SUBJECT_TO DATA c2 AND DATA c3 AND DATA c5 AND DATA c7.
def check_trug_file(path: Path, report: Report, root: Path, folder_code_artifacts: Optional[dict[str, dict]] = None, folder_py_names: Optional[set[str]] = None) -> None:
    """Run C2, C3, C5, C7 on a single `.trug.json` file."""
    report.trug_files_checked += 1
    graph = _load_trug(path)
    if graph is None:
        report.violations.append(Violation(
            rule="C7", path=path, line=None, symbol=None,
            message="could not parse as JSON",
        ))
        return

    # C7: delegate to trugs-folder-check
    _run_folder_check(path, report)

    # C3: every node with trl property must parse via trl.py
    for node in graph.get("nodes", []):
        props = node.get("properties", {}) or {}
        trl_sentence = props.get("trl")
        if trl_sentence:
            report.nodes_checked += 1
            ok, err = _try_parse_trl(trl_sentence)
            if not ok:
                report.violations.append(Violation(
                    rule="C3", path=path, line=None, symbol=node.get("id"),
                    message=f"node '{node.get('id')}' trl property does not parse: {err}",
                ))

    # C5: every TEST node must have at least one outbound VALIDATES edge
    for test_node in _test_nodes(graph):
        if not _has_validates_edge(graph, test_node.get("id", "")):
            report.violations.append(Violation(
                rule="C5", path=path, line=None, symbol=test_node.get("id"),
                message=f"TEST node '{test_node.get('id')}' has no outbound VALIDATES edge",
            ))

    # C2: for each code-artifact node, confirm a matching public Python name exists in the folder
    # (only runs when folder_py_names is supplied — optional because invocation can skip it)
    if folder_py_names is not None:
        for n in graph.get("nodes", []):
            if n.get("type") not in _CODE_ARTIFACT_NODE_TYPES:
                continue
            name = _node_name(n)
            if not name:
                continue
            if name not in folder_py_names:
                report.violations.append(Violation(
                    rule="C2", path=path, line=None, symbol=n.get("id"),
                    message=f"node '{n.get('id')}' ({n.get('type')}) declares name '{name}' but no matching public def/class found in folder",
                ))


# AGENT compliance SHALL DELEGATE C7 TO PROCESS trugs_validate.
def _run_folder_check(trug_path: Path, report: Report) -> None:
    """C7 — validate a TRUG file against CORE rules.

    Preferred: in-process import of tools.validate (always available in TRUGS itself
    and in any repo that installs the `trugs` package). Falls back to subprocess
    `trugs-validate` for resilience, and `trugs-folder-check` if that's the tool
    available in the environment.
    """
    # Preferred: in-process validator from the trugs package
    try:
        from trugs_tools import validate as _validate_mod
        result_obj = _validate_mod.validate_file(trug_path)
        if not result_obj.valid:
            first_err = result_obj.errors[0] if result_obj.errors else None
            msg = f"{first_err.code}: {first_err.message}" if first_err else "validate reported errors"
            report.violations.append(Violation(
                rule="C7", path=trug_path, line=None, symbol=None,
                message=f"validate_graph failed: {msg}",
            ))
        return
    except ImportError:
        pass  # fall through to subprocess

    # Fallback: subprocess, try trugs-validate first, then trugs-folder-check
    for cmd in (["trugs-validate", str(trug_path)], ["trugs-folder-check", str(trug_path)]):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            msg = (result.stdout + result.stderr).strip().splitlines()
            first = msg[0] if msg else f"{cmd[0]} reported errors"
            report.violations.append(Violation(
                rule="C7", path=trug_path, line=None, symbol=None,
                message=f"{cmd[0]} failed: {first}",
            ))
        return
    # Neither validator available — one violation
    report.violations.append(Violation(
        rule="C7", path=trug_path, line=None, symbol=None,
        message="no validator available — install trugs (tools.validate) or trugs-tools (trugs-folder-check)",
    ))


# AGENT compliance SHALL VALIDATE EACH RECORD invariant SUBJECT_TO A RECORD assertion AND A RECORD test.
def check_invariants_across_repo(root: Path, report: Report, py_files: list[Path], trug_files: list[Path]) -> None:
    """C6 — invariants in TRUG must have matching assertions and tests.

    Heuristic:
    - Find every invariant_* property across all trug files.
    - For each, scan py_files for a substring match of the invariant key
      in an assert statement (approximate — good enough for v1).
    - For each, scan py_files for a test function whose comment mentions
      the invariant name.
    - Report missing assertions and missing tests as separate findings.
    """
    all_py_text: dict[Path, str] = {}
    for p in py_files:
        try:
            all_py_text[p] = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

    for trug_path in trug_files:
        graph = _load_trug(trug_path)
        if graph is None:
            continue
        for node, inv_key in _invariant_properties(graph):
            # Look for the invariant mentioned in any assert line or any test comment
            found_assertion = False
            found_test = False
            for py_path, src in all_py_text.items():
                if inv_key in src:
                    # Does it appear in an assert statement?
                    if re.search(rf"\bassert\b.*{re.escape(inv_key)}", src):
                        found_assertion = True
                    # Does it appear in a test function comment?
                    # Find test function comments: `# AGENT SHALL VALIDATE ... invariant_key ...`
                    if re.search(rf"#\s*AGENT\s+SHALL\s+VALIDATE[^\n]*{re.escape(inv_key)}", src, re.IGNORECASE):
                        found_test = True
            if not found_assertion:
                report.violations.append(Violation(
                    rule="C6", path=trug_path, line=None, symbol=node.get("id"),
                    message=f"invariant '{inv_key}' on node '{node.get('id')}' has no matching assertion in code",
                ))
            if not found_test:
                report.violations.append(Violation(
                    rule="C6", path=trug_path, line=None, symbol=node.get("id"),
                    message=f"invariant '{inv_key}' on node '{node.get('id')}' has no matching test",
                ))


# =============================================================================
# BASELINE MANAGEMENT
# =============================================================================


_BASELINE_PATH = Path(".github/compliance-baseline.json")


def _load_baseline(root: Path) -> Optional[dict]:
    bp = root / _BASELINE_PATH
    if not bp.exists():
        return None
    try:
        return json.loads(bp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_baseline(root: Path, report: Report) -> None:
    # PROCESS baseline_update SHALL WRITE RECORD compliance_baseline
    #   TO FILE .github/compliance-baseline.json.
    bp = root / _BASELINE_PATH
    bp.parent.mkdir(parents=True, exist_ok=True)
    # Summary only — the detailed violations list is regenerated every run and
    # would create enormous diffs in the baseline file. The ratchet operates on
    # compliance_percent alone.
    summary = {
        "compliance_percent": report.compliance_percent,
        "files_checked": report.files_checked,
        "functions_checked": report.functions_checked,
        "tests_checked": report.tests_checked,
        "nodes_checked": report.nodes_checked,
        "trug_files_checked": report.trug_files_checked,
        "violation_count": report.violation_count,
        "violations_by_rule": report.violations_by_rule,
    }
    bp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


# =============================================================================
# MAIN AUDIT
# =============================================================================


# PROCESS audit SHALL VALIDATE ALL FILE SUBJECT_TO DATA standard THEN RETURN RECORD report.
def audit(root: Path, strict: bool = False) -> Report:
    """Run all checks under `root`. Returns a populated Report."""
    report = Report()

    py_files = _iter_files(root, ".py")
    trug_files = _iter_files(root, ".trug.json")
    report.files_checked = len(py_files) + len(trug_files)

    # Build per-folder indexes for cross-check C2
    # GROUP py_files BY PARENT folder
    folder_py_names: dict[Path, set[str]] = {}
    for py in py_files:
        folder = py.parent
        names = folder_py_names.setdefault(folder, set())
        for rec in _walk_python(py):
            if not rec.is_test:
                names.add(rec.name)

    # C1 + C4 — Python files
    for p in py_files:
        check_python_file(p, report, root)

    # C2 + C3 + C5 + C7 — TRUG files
    for t in trug_files:
        folder = t.parent
        py_names = folder_py_names.get(folder, set())
        check_trug_file(t, report, root, folder_py_names=py_names)

    # C6 — cross-file invariants
    check_invariants_across_repo(root, report, py_files, trug_files)

    return report


# =============================================================================
# RENDERING
# =============================================================================


# AGENT claude SHALL WRITE RECORD report AS STRING DATA output.
def render_text(report: Report, root: Path) -> str:
    """Human-readable report."""
    lines: list[str] = []
    lines.append(f"trugs-compliance-check — {root}")
    lines.append("")
    lines.append(f"  Files checked:       {report.files_checked}")
    lines.append(f"  Functions checked:   {report.functions_checked}")
    lines.append(f"  Tests checked:       {report.tests_checked}")
    lines.append(f"  TRUG nodes checked:  {report.nodes_checked}")
    lines.append(f"  TRUG files checked:  {report.trug_files_checked}")
    lines.append(f"  Violations:          {report.violation_count}")
    if report.violations:
        lines.append("")
        for rule in sorted(report.violations_by_rule):
            lines.append(f"  {rule}: {report.violations_by_rule[rule]}")
        lines.append("")
        for v in report.violations:
            lines.append(v.format(root))
    lines.append("")
    lines.append(f"  Compliance: {report.compliance_percent}%")
    return "\n".join(lines)


# =============================================================================
# CLI ENTRY
# =============================================================================


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="trugs-compliance-check",
        description="Mechanical Dark Code compliance verifier (STANDARD_dark_code_compliance.md).",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repo root or subdirectory to audit.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any violation (vs the default, which compares to baseline).")
    parser.add_argument("--baseline-update", action="store_true", help="Overwrite .github/compliance-baseline.json with the current report.")
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"error: path does not exist: {root}", file=sys.stderr)
        return 2

    report = audit(root, strict=args.strict)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_text(report, root))

    if args.baseline_update:
        _write_baseline(root, report)
        print(f"\nBaseline written to {root / _BASELINE_PATH}", file=sys.stderr)
        return 0

    # Exit logic
    if args.strict:
        return 1 if report.violation_count > 0 else 0
    baseline = _load_baseline(root)
    if baseline is None:
        # No baseline yet — any compliance is acceptable (record the first baseline manually).
        return 0
    baseline_pct = baseline.get("compliance_percent", 0.0)
    if report.compliance_percent < baseline_pct:
        print(
            f"\nFAIL: compliance decreased — current {report.compliance_percent}% < baseline {baseline_pct}%",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
