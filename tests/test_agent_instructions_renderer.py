"""Tests for agent_instructions_renderer — agent_instructions.trug.json → copilot-instructions.md."""

import json
import pytest
from pathlib import Path

from trugs_tools.agent_instructions_renderer import (
    render_agent_instructions,
    GENERATED_HEADER,
    _load_trug,
)


# ─── Fixtures ─────────────────────────────────────────────────────────


REPO_ROOT = Path(__file__).parent.parent.parent


# AGENT claude SHALL DEFINE FUNCTION minimal_trug.
@pytest.fixture
def minimal_trug():
    """Minimal agent_instructions TRUG with one node of each key type."""
    return {
        "meta": {
            "id": "agent_instructions",
            "type": "agent_instructions",
            "version": "1.0.0",
            "label": "Test Agent Instructions",
        },
        "nodes": [
            {
                "id": "tutorial_what_is_a_trug",
                "type": "STANDARD",
                "label": "What Is a TRUG",
                "properties": {
                    "severity": "FOUNDATIONAL",
                    "description": "TRUG is a JSON graph.",
                    "definition": "Three components: nodes, edges, hierarchy.",
                    "key_principle": "The TRUG indexes reality.",
                },
            },
            {
                "id": "protected_paths",
                "type": "CONSTRAINT",
                "label": "Protected Paths",
                "properties": {
                    "severity": "HARD",
                    "description": "Never modify these paths.",
                    "paths": ["PATENT/", ".env/"],
                },
            },
            {
                "id": "rule_branching",
                "type": "RULE",
                "label": "Branching Rules",
                "properties": {
                    "severity": "HARD",
                    "universal_rule": "All changes need a branch.",
                    "branch_steps": ["Create issue", "Create branch", "Create PR"],
                },
            },
            {
                "id": "convention_archive",
                "type": "CONVENTION",
                "label": "Archive Convention",
                "properties": {
                    "prefix": "zzz_",
                    "description": "Files prefixed with zzz_ are archived.",
                    "llm_rule": "Ignore zzz_ files.",
                    "trug_rule": "Never include zzz_ files in TRUGs.",
                    "rationale": "Invisible to the graph.",
                },
            },
            {
                "id": "workflow_interactive",
                "type": "WORKFLOW",
                "label": "Interactive Development",
                "properties": {
                    "description": "Code freely, update trug after.",
                },
            },
            {
                "id": "reference_aaa",
                "type": "REFERENCE",
                "label": "AAA Reference",
                "properties": {
                    "path": "TRUGS_AAA/REFERENCE_aaa_reference.md",
                },
            },
        ],
        "edges": [],
    }


# AGENT claude SHALL DEFINE FUNCTION real_trug_path.
@pytest.fixture
def real_trug_path():
    """Path to the real agent_instructions.trug.json in this repo."""
    return REPO_ROOT / ".github" / "agent_instructions.trug.json"


# ─── _load_trug tests ─────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS test_load_trug_from_dict.
def test_load_trug_from_dict(minimal_trug):
    result = _load_trug(minimal_trug)
    assert result is minimal_trug


# AGENT SHALL VALIDATE PROCESS test_load_trug_from_path.
def test_load_trug_from_path(tmp_path, minimal_trug):
    p = tmp_path / "test.trug.json"
    p.write_text(json.dumps(minimal_trug), encoding="utf-8")
    result = _load_trug(p)
    assert result["meta"]["id"] == "agent_instructions"


# AGENT SHALL VALIDATE PROCESS test_load_trug_from_str_path.
def test_load_trug_from_str_path(tmp_path, minimal_trug):
    p = tmp_path / "test.trug.json"
    p.write_text(json.dumps(minimal_trug), encoding="utf-8")
    result = _load_trug(str(p))
    assert result["meta"]["id"] == "agent_instructions"


# AGENT SHALL VALIDATE PROCESS test_load_trug_invalid_type.
def test_load_trug_invalid_type():
    with pytest.raises(TypeError, match="Expected dict, str, or Path"):
        _load_trug(42)


# ─── render_agent_instructions tests ─────────────────────────────────


# AGENT SHALL VALIDATE PROCESS test_output_includes_generated_header.
def test_output_includes_generated_header(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert GENERATED_HEADER in out


# AGENT SHALL VALIDATE PROCESS test_output_includes_source_comment.
def test_output_includes_source_comment(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert "SOURCE OF TRUTH: .github/agent_instructions.trug.json" in out


# AGENT SHALL VALIDATE PROCESS test_output_includes_title.
def test_output_includes_title(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert "# TRUGS_DEVELOPMENT: Instructions for LLM and CoPilot Agents." in out


# AGENT SHALL VALIDATE PROCESS test_output_ends_with_newline.
def test_output_ends_with_newline(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert out.endswith("\n")


# AGENT SHALL VALIDATE PROCESS test_deterministic_output.
def test_deterministic_output(minimal_trug):
    """Same input produces identical output."""
    out1 = render_agent_instructions(minimal_trug)
    out2 = render_agent_instructions(minimal_trug)
    assert out1 == out2


# AGENT SHALL VALIDATE PROCESS test_what_is_a_trug_section_rendered.
def test_what_is_a_trug_section_rendered(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert "## What Is a TRUG" in out
    assert "TRUG is a JSON graph." in out
    assert "The TRUG indexes reality." in out


# AGENT SHALL VALIDATE PROCESS test_protected_section_rendered.
def test_protected_section_rendered(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert "## PROTECTED - DO NOT MODIFY" in out
    assert "`PATENT/`" in out
    assert "`.env/`" in out


# AGENT SHALL VALIDATE PROCESS test_branching_rules_section_rendered.
def test_branching_rules_section_rendered(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert "## BRANCHING RULES (HARD RULE)" in out
    assert "All changes need a branch." in out
    assert "1. Create issue" in out


# AGENT SHALL VALIDATE PROCESS test_archive_convention_section_rendered.
def test_archive_convention_section_rendered(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert "## ARCHIVE CONVENTION" in out
    assert "`zzz_`" in out


# AGENT SHALL VALIDATE PROCESS test_project_org_section_rendered.
def test_project_org_section_rendered(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert "## Project Organization & Agentic Coding" in out
    assert "Interactive Development" in out


# AGENT SHALL VALIDATE PROCESS test_references_section_rendered.
def test_references_section_rendered(minimal_trug):
    out = render_agent_instructions(minimal_trug)
    assert "## References" in out
    assert "AAA Reference" in out
    assert "TRUGS_AAA/REFERENCE_aaa_reference.md" in out


# AGENT SHALL VALIDATE PROCESS test_section_order.
def test_section_order(minimal_trug):
    """Key sections appear in the expected order."""
    out = render_agent_instructions(minimal_trug)
    trug_pos = out.find("## What Is a TRUG")
    protected_pos = out.find("## PROTECTED")
    branching_pos = out.find("## BRANCHING RULES")
    refs_pos = out.find("## References")
    assert trug_pos < protected_pos < branching_pos < refs_pos


# ─── Real TRUG tests ──────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS test_render_from_real_trug.
def test_render_from_real_trug(real_trug_path):
    """Smoke test: render the real agent_instructions.trug.json without error."""
    if not real_trug_path.exists():
        pytest.skip("Real TRUG not found — skipping integration test")
    out = render_agent_instructions(real_trug_path)
    assert len(out) > 500
    assert "## What Is a TRUG" in out
    assert "## BRANCHING RULES (HARD RULE)" in out
    assert "## DOCUMENTATION STANDARDS" in out
    assert "## EXECUTION RULES" in out
    assert "## SUB-ISSUES" in out
    assert "## References" in out


# AGENT SHALL VALIDATE PROCESS test_real_trug_has_all_major_sections.
def test_real_trug_has_all_major_sections(real_trug_path):
    """The rendered output from the real TRUG must contain all expected sections."""
    if not real_trug_path.exists():
        pytest.skip("Real TRUG not found")
    out = render_agent_instructions(real_trug_path)

    expected_sections = [
        "## What Is a TRUG",
        "## PROTECTED - DO NOT MODIFY",
        "## Project Organization & Agentic Coding",
        "## DOCUMENTATION STANDARDS",
        "### Four-File Pattern Per Folder",
        "## BRANCHING RULES (HARD RULE)",
        "## DOCUMENT NAMING CONVENTION",
        "## ARCHIVE CONVENTION",
        "## FOLDER TRUG BUILD RULES (HARD RULE)",
        "## EXECUTION RULES",
        "## SUB-ISSUES",
        "## Key CLI Commands",
        "## References",
    ]
    for section in expected_sections:
        assert section in out, f"Missing section: {section!r}"


# ─── CLI command tests ────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS test_cli_dry_run.
def test_cli_dry_run(tmp_path, minimal_trug, capsys):
    """--dry-run prints to stdout and does not create output file."""
    import json as json_mod
    from trugs_tools.cli import agent_render_command

    trug_file = tmp_path / "agent_instructions.trug.json"
    trug_file.write_text(json_mod.dumps(minimal_trug), encoding="utf-8")
    output_file = tmp_path / "copilot-instructions.md"

    rc = agent_render_command([
        "--input", str(trug_file),
        "--output", str(output_file),
        "--dry-run",
    ])
    assert rc == 0
    assert not output_file.exists(), "dry-run must not write file"

    captured = capsys.readouterr()
    assert "## What Is a TRUG" in captured.out


# AGENT SHALL VALIDATE PROCESS test_cli_writes_output_file.
def test_cli_writes_output_file(tmp_path, minimal_trug):
    """Without --dry-run, the output file is written."""
    import json as json_mod
    from trugs_tools.cli import agent_render_command

    trug_file = tmp_path / "agent_instructions.trug.json"
    trug_file.write_text(json_mod.dumps(minimal_trug), encoding="utf-8")
    output_file = tmp_path / "out" / "copilot-instructions.md"

    rc = agent_render_command([
        "--input", str(trug_file),
        "--output", str(output_file),
    ])
    assert rc == 0
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "## What Is a TRUG" in content


# AGENT SHALL VALIDATE PROCESS test_cli_missing_input_returns_exit_1.
def test_cli_missing_input_returns_exit_1(tmp_path):
    """Missing input file → exit code 1."""
    from trugs_tools.cli import agent_render_command

    rc = agent_render_command([
        "--input", str(tmp_path / "nonexistent.trug.json"),
        "--output", str(tmp_path / "out.md"),
    ])
    assert rc == 1
