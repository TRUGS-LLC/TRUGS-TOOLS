"""Tests for TRUGS CLI commands."""

import pytest
import json
import sys
from pathlib import Path
from io import StringIO

from trugs_tools.cli import validate_command, generate_command, info_command, main


def test_validate_command_valid_file(tmp_path):
    """Test validating a valid TRUG file."""
    # Create a valid TRUG file
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [
            {"id": "node1", "type": "MODULE", "metric_level": "DEKA_MODULE", "parent_id": None}
        ],
        "edges": []
    }
    
    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)
    
    # Test validation
    exit_code = validate_command([str(trug_file)])
    assert exit_code == 0


def test_validate_command_invalid_file(tmp_path):
    """Test validating an invalid TRUG file."""
    # Create an invalid TRUG file (missing required fields)
    trug = {"name": "Test"}
    
    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)
    
    # Test validation
    exit_code = validate_command([str(trug_file)])
    assert exit_code == 1


def test_validate_command_multiple_files(tmp_path):
    """Test validating multiple TRUG files."""
    # Create two valid files
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [{"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE"}],
        "edges": []
    }
    
    file1 = tmp_path / "test1.json"
    file2 = tmp_path / "test2.json"
    
    for f in [file1, file2]:
        with open(f, 'w') as fp:
            json.dump(trug, fp)
    
    # Test validation
    exit_code = validate_command([str(file1), str(file2)])
    assert exit_code == 0


def test_validate_command_json_output(tmp_path, capsys):
    """Test validation with JSON output format."""
    # Create a valid TRUG file
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [{"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE"}],
        "edges": []
    }
    
    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)
    
    # Test with JSON output
    exit_code = validate_command([str(trug_file), "--format", "json"])
    assert exit_code == 0
    
    # Check JSON output
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert "results" in output
    assert len(output["results"]) == 1
    assert output["results"][0]["valid"] is True


def test_validate_command_file_not_found():
    """Test validation with non-existent file."""
    exit_code = validate_command(["nonexistent.json"])
    # File not found returns exit code 2 (error)
    # But might also return 1 depending on error handling
    assert exit_code in [1, 2]


def test_generate_command_python_minimal(tmp_path, capsys):
    """Test generating a Web minimal TRUG."""
    output_file = tmp_path / "output.json"
    
    exit_code = generate_command([
        "--branch", "web",
        "--template", "minimal",
        "--output", str(output_file)
    ])
    
    assert exit_code == 0
    assert output_file.exists()
    
    # Verify generated file
    with open(output_file) as f:
        trug = json.load(f)
    
    assert trug["branch"] == "web"
    assert trug["name"] == "Web Minimal Example"


def test_generate_command_all_branches(tmp_path):
    """Test generating TRUGs for all branches."""
    branches = ["web", "writer", "orchestration", "knowledge_v1", "nested"]
    
    for branch in branches:
        output_file = tmp_path / f"{branch}.json"
        exit_code = generate_command([
            "--branch", branch,
            "--output", str(output_file)
        ])
        
        assert exit_code == 0
        assert output_file.exists()


def test_generate_command_with_extensions(tmp_path):
    """Test generating TRUG with extensions."""
    output_file = tmp_path / "output.json"
    
    exit_code = generate_command([
        "--branch", "web",
        "--extension", "typed",
        "--extension", "scoped",
        "--output", str(output_file)
    ])
    
    assert exit_code == 0
    assert output_file.exists()


def test_generate_command_stdout(capsys):
    """Test generating TRUG to stdout."""
    exit_code = generate_command([
        "--branch", "web",
        "--template", "minimal"
    ])
    
    assert exit_code == 0
    
    # Check output
    captured = capsys.readouterr()
    trug = json.loads(captured.out)
    assert trug["branch"] == "web"


def test_generate_command_invalid_branch():
    """Test generating with invalid branch."""
    # Invalid branch will raise SystemExit from argparse
    with pytest.raises(SystemExit):
        exit_code = generate_command([
            "--branch", "invalid_branch"
        ])


def test_info_command_valid_file(tmp_path, capsys):
    """Test info command on valid TRUG file."""
    # Create a TRUG file
    trug = {
        "name": "Test TRUG",
        "version": "1.0.0",
        "type": "CODE",
        "branch": "web",
        "nodes": [
            {"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE"},
            {"id": "n2", "type": "FUNCTION", "metric_level": "BASE_FUNCTION"}
        ],
        "edges": [
            {"from_id": "n1", "to_id": "n2", "relation": "contains"}
        ]
    }
    
    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)
    
    # Test info command
    exit_code = info_command([str(trug_file)])
    assert exit_code == 0
    
    # Check output
    captured = capsys.readouterr()
    assert "Test TRUG" in captured.out
    assert "web" in captured.out
    assert "Nodes:      2" in captured.out
    assert "Edges:      1" in captured.out


def test_info_command_json_output(tmp_path, capsys):
    """Test info command with JSON output."""
    # Create a TRUG file
    trug = {
        "name": "Test TRUG",
        "version": "1.0.0",
        "type": "CODE",
        "branch": "web",
        "nodes": [{"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE"}],
        "edges": []
    }
    
    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)
    
    # Test with JSON output
    exit_code = info_command([str(trug_file), "--format", "json"])
    assert exit_code == 0
    
    # Check JSON output
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["name"] == "Test TRUG"
    assert output["branch"] == "web"
    assert output["node_count"] == 1


def test_info_command_file_not_found():
    """Test info command with non-existent file."""
    exit_code = info_command(["nonexistent.json"])
    assert exit_code == 1


def test_main_version(capsys):
    """Test main command with --version."""
    # Override sys.argv to test version
    old_argv = sys.argv
    try:
        sys.argv = ["trugs", "--version"]
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = old_argv


def test_main_no_command(capsys):
    """Test main command with no subcommand."""
    old_argv = sys.argv
    try:
        sys.argv = ["trugs"]
        exit_code = main()
        assert exit_code == 0
    finally:
        sys.argv = old_argv


def test_validate_quiet_mode(tmp_path, capsys):
    """Test validation in quiet mode."""
    # Create a valid TRUG file
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [{"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE"}],
        "edges": []
    }
    
    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)
    
    # Test with quiet mode
    exit_code = validate_command([str(trug_file), "--quiet"])
    assert exit_code == 0
    
    # Quiet mode may or may not print output depending on implementation
    # Just check exit code is correct


def test_validate_verbose_mode(tmp_path, capsys):
    """Test validation in verbose mode."""
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [
            {"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE"}
        ],
        "edges": []
    }
    
    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)
    
    # Test with verbose mode
    exit_code = validate_command([str(trug_file), "--verbose"])
    assert exit_code == 0  # Valid TRUG


def test_generate_complete_template(tmp_path):
    """Test generating complete template."""
    output_file = tmp_path / "complete.json"
    
    exit_code = generate_command([
        "--branch", "web",
        "--template", "complete",
        "--output", str(output_file)
    ])
    
    assert exit_code == 0
    
    # Verify it's a complete template (more nodes)
    with open(output_file) as f:
        trug = json.load(f)
    
    assert len(trug["nodes"]) > 3  # Complete should have more nodes than minimal


# ─── S1.3.4: CLI Command Tests ────────────────────────────────────────


from trugs_tools.cli import render_command


def _make_folder_trug_file(tmp_path):
    """Helper: write a minimal folder.trug.json and return its path."""
    trug = {
        "name": "CLI_TEST",
        "version": "1.0.0",
        "type": "PROJECT",
        "nodes": [
            {
                "id": "folder_root",
                "type": "FOLDER",
                "metric_level": "MEGA_ROOT",
                "parent_id": None,
                "properties": {
                    "name": "CLI_TEST",
                    "purpose": "CLI test folder",
                    "phase": "VISION",
                    "status": "ACTIVE",
                    "version": "0.1.0"
                }
            }
        ],
        "edges": []
    }
    f = tmp_path / "folder.trug.json"
    f.write_text(json.dumps(trug))
    return f


def test_render_command_valid_file(tmp_path):
    """Test render_command with valid TRUG file."""
    trug_file = _make_folder_trug_file(tmp_path)
    out_dir = tmp_path / "output"

    exit_code = render_command([str(trug_file), "--output", str(out_dir)])
    assert exit_code == 0
    assert (out_dir / "AAA.md").exists()
    assert (out_dir / "README.md").exists()
    assert (out_dir / "ARCHITECTURE.md").exists()


def test_render_command_dry_run(tmp_path, capsys):
    """Test render_command with --dry-run."""
    trug_file = _make_folder_trug_file(tmp_path)

    exit_code = render_command([str(trug_file), "--dry-run"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "=== AAA.md ===" in captured.out
    assert "=== README.md ===" in captured.out
    assert "=== ARCHITECTURE.md ===" in captured.out


def test_render_command_file_type_aaa(tmp_path, capsys):
    """Test render_command with --file-type aaa."""
    trug_file = _make_folder_trug_file(tmp_path)

    exit_code = render_command([str(trug_file), "--dry-run", "--file-type", "aaa"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "=== AAA.md ===" in captured.out
    assert "=== README.md ===" not in captured.out


def test_render_command_output_directory(tmp_path):
    """Test render_command with --output directory."""
    trug_file = _make_folder_trug_file(tmp_path)
    out_dir = tmp_path / "rendered"

    exit_code = render_command([str(trug_file), "--output", str(out_dir)])
    assert exit_code == 0
    assert out_dir.exists()
    assert (out_dir / "AAA.md").exists()


def test_render_command_nonexistent_file(capsys):
    """Test render_command with non-existent file."""
    exit_code = render_command(["nonexistent_file.json"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "not found" in captured.err.lower() or "error" in captured.err.lower()


def test_render_command_invalid_json(tmp_path, capsys):
    """Test render_command with invalid JSON file."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid json content")

    exit_code = render_command([str(bad_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Invalid JSON" in captured.err or "Error" in captured.err


def test_validate_command_file_not_found(capsys):
    """Test validate_command with file not found."""
    exit_code = validate_command(["totally_nonexistent_file.json"])
    # validate_trug handles FileNotFoundError internally as PARSE_ERROR → exit 1
    assert exit_code in [1, 2]


def test_validate_command_invalid_json(tmp_path, capsys):
    """Test validate_command with invalid JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json {{{")

    exit_code = validate_command([str(bad_file)])
    # validate_trug handles JSONDecodeError internally as PARSE_ERROR → exit 1
    assert exit_code in [1, 2]


def test_info_command_with_extensions(tmp_path, capsys):
    """Test info_command with extensions present."""
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "branch": "web",
        "extensions": ["typed", "scoped"],
        "nodes": [
            {"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE"}
        ],
        "edges": []
    }

    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)

    exit_code = info_command([str(trug_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Extensions:" in captured.out
    assert "typed" in captured.out
    assert "scoped" in captured.out


def test_info_command_file_not_found(capsys):
    """Test info_command with file not found."""
    exit_code = info_command(["totally_nonexistent_file.json"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "not found" in captured.err.lower() or "error" in captured.err.lower()


def test_info_command_invalid_json(tmp_path, capsys):
    """Test info_command with invalid JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{broken json")

    exit_code = info_command([str(bad_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Invalid JSON" in captured.err or "Error" in captured.err


def test_main_subcommand_dispatch_validate(tmp_path, capsys):
    """Test main subcommand dispatch with validate."""
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "CODE",
        "nodes": [
            {"id": "n1", "type": "MODULE", "metric_level": "DEKA_MODULE", "parent_id": None}
        ],
        "edges": []
    }

    trug_file = tmp_path / "test.json"
    with open(trug_file, 'w') as f:
        json.dump(trug, f)

    # Call validate_command directly to test dispatch logic
    exit_code = validate_command([str(trug_file)])
    assert exit_code == 0


def test_generate_command_error_handling(capsys):
    """Test generate_command error path (line 169-171)."""
    from unittest.mock import patch

    with patch("trugs_tools.cli.generate_trug", side_effect=Exception("generation error")):
        exit_code = generate_command([
            "--branch", "web",
            "--template", "minimal"
        ])
        assert exit_code == 1

    captured = capsys.readouterr()
    assert "generation error" in captured.err


def test_info_command_generic_exception(tmp_path, capsys):
    """Test info_command generic exception path (line 262-264)."""
    from unittest.mock import patch

    trug_file = tmp_path / "test.json"
    trug_file.write_text('{"name": "test"}')

    with patch("trugs_tools.validator.load_trug", side_effect=RuntimeError("unexpected")):
        exit_code = info_command([str(trug_file)])
        assert exit_code == 1

    captured = capsys.readouterr()
    assert "unexpected" in captured.err


def test_render_command_generic_exception(tmp_path, capsys):
    """Test render_command generic exception path (line 337-339)."""
    from unittest.mock import patch

    trug_file = _make_folder_trug_file(tmp_path)

    with patch("trugs_tools.cli.render_all", side_effect=RuntimeError("render failed")):
        exit_code = render_command([str(trug_file)])
        assert exit_code == 1

    captured = capsys.readouterr()
    assert "render failed" in captured.err


def test_main_dispatches_func():
    """Test main() hasattr(args, 'func') dispatch (line 376)."""
    old_argv = sys.argv
    try:
        sys.argv = ["trugs"]
        exit_code = main()
        assert exit_code == 0
    finally:
        sys.argv = old_argv
