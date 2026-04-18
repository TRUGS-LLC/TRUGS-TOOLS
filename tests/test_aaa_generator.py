"""Tests for trugs_tools.aaa_generator."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from trugs_tools.aaa_generator import (
    _compose_aaa,
    _detect_owner_repo,
    _folder_name_from_label,
    _format_date,
    _next_link,
    _linked_pr_from_timeline,
    _normalize_headers,
    _sub_issue_section,
    _write_aaa,
    _archive_aaa,
    generate_all,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_folder_name_from_label():
    assert _folder_name_from_label("folder:TRUGS_TOOLS") == "TRUGS_TOOLS"
    assert _folder_name_from_label("folder:TRUGS_AAA") == "TRUGS_AAA"


def test_format_date_iso():
    assert _format_date("2026-02-25T12:00:00Z") == "2026-02-25"


def test_format_date_none():
    assert _format_date(None) == ""


def test_format_date_empty():
    assert _format_date("") == ""


def test_next_link_present():
    header = '<https://api.github.com/repos/X/Y/labels?page=2>; rel="next", <https://api.github.com/repos/X/Y/labels?page=5>; rel="last"'
    assert _next_link(header) == "https://api.github.com/repos/X/Y/labels?page=2"


def test_next_link_absent():
    header = '<https://api.github.com/repos/X/Y/labels?page=1>; rel="first"'
    assert _next_link(header) is None


def test_next_link_empty():
    assert _next_link("") is None


def test_linked_pr_none_when_no_events():
    assert _linked_pr_from_timeline([]) is None


def test_linked_pr_from_cross_referenced():
    events = [
        {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "number": 99,
                    "html_url": "https://github.com/X/Y/pull/99",
                    "state": "closed",
                    "pull_request": {"merged_at": "2026-01-15T10:00:00Z"},
                }
            },
        }
    ]
    pr = _linked_pr_from_timeline(events)
    assert pr is not None
    assert pr["number"] == 99
    assert pr["merged_at"] == "2026-01-15T10:00:00Z"


def test_linked_pr_skips_non_pr_cross_refs():
    events = [
        {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "number": 50,
                    "html_url": "https://github.com/X/Y/issues/50",
                    "state": "open",
                    # No "pull_request" key → not a PR
                }
            },
        }
    ]
    assert _linked_pr_from_timeline(events) is None


# ---------------------------------------------------------------------------
# _normalize_headers
# ---------------------------------------------------------------------------


def test_normalize_headers_strips_parenthetical():
    body = "## ARCHITECTURE (Issue TRUG)\nsome content"
    assert _normalize_headers(body) == "## ARCHITECTURE\nsome content"


def test_normalize_headers_strips_multiple():
    body = "## VISION (Phase 1)\n\n## FEASIBILITY (check)\n"
    result = _normalize_headers(body)
    assert "## VISION\n" in result
    assert "## FEASIBILITY\n" in result


def test_normalize_headers_leaves_plain_headers():
    body = "## VISION\n\n## CODING\n"
    assert _normalize_headers(body) == body


def test_normalize_headers_leaves_lowercase_headers():
    # Only all-caps headers should be normalized
    body = "## My Header (note)\n"
    # 'My' starts with uppercase but has lowercase — won't match [A-Z][A-Z_\s]*
    # Actually it's: ## M starts uppercase, then y is lowercase — let's check
    # The pattern is [A-Z][A-Z_\s]* so 'My Header' won't match (y is lowercase)
    assert _normalize_headers(body) == body


def test_normalize_headers_empty():
    assert _normalize_headers("") == ""


# ---------------------------------------------------------------------------
# _detect_owner_repo
# ---------------------------------------------------------------------------


def test_detect_owner_repo_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_OWNER", "TestOwner")
    monkeypatch.setenv("GH_REPO", "TestRepo")
    owner, repo = _detect_owner_repo(str(tmp_path))
    assert owner == "TestOwner"
    assert repo == "TestRepo"


def test_detect_owner_repo_from_git_remote(tmp_path):
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/SomeOwner/SomeRepo.git"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    owner, repo = _detect_owner_repo(str(tmp_path))
    assert owner == "SomeOwner"
    assert repo == "SomeRepo"


def test_detect_owner_repo_from_ssh_remote(tmp_path):
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:OtherOwner/OtherRepo.git"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    owner, repo = _detect_owner_repo(str(tmp_path))
    assert owner == "OtherOwner"
    assert repo == "OtherRepo"


def test_detect_owner_repo_raises_when_no_remote(tmp_path):
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    with pytest.raises(RuntimeError, match="Could not detect owner/repo"):
        _detect_owner_repo(str(tmp_path))


# ---------------------------------------------------------------------------
# _sub_issue_section
# ---------------------------------------------------------------------------


@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
def test_sub_issue_section_open_no_pr(mock_tl):
    sub = {"number": 10, "title": "Do something", "state": "open", "body": "Details here"}
    section = _sub_issue_section(sub, "X", "Y")
    assert "### #10 — Do something" in section
    assert "🟡 Open" in section
    assert "Details here" in section


@patch(
    "trugs_tools.aaa_generator._timeline_events",
    return_value=[
        {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "number": 55,
                    "html_url": "https://github.com/X/Y/pull/55",
                    "state": "closed",
                    "pull_request": {"merged_at": "2026-02-01T08:00:00Z"},
                }
            },
        }
    ],
)
def test_sub_issue_section_closed_with_pr(mock_tl):
    sub = {"number": 20, "title": "Fixed bug", "state": "closed", "body": ""}
    section = _sub_issue_section(sub, "X", "Y")
    assert "✅ Closed" in section
    assert "PR #55 merged 2026-02-01" in section


# ---------------------------------------------------------------------------
# _compose_aaa
# ---------------------------------------------------------------------------


@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
def test_compose_aaa_structure(mock_tl):
    issue = {
        "number": 100,
        "title": "Build something",
        "state": "open",
        "body": "## VISION\nDo great things.",
        "updated_at": "2026-02-20T00:00:00Z",
    }
    sub_issues = [
        {"number": 101, "title": "Sub task 1", "state": "open", "body": "Sub body"},
    ]
    content = _compose_aaa("TRUGS_TOOLS", issue, sub_issues, "X", "Y")
    assert content.startswith("# TRUGS_TOOLS/")
    assert "**Issue:** #100 — Build something" in content
    assert "**Status:** Open" in content
    assert "**Last Updated:** 2026-02-20" in content
    assert "## VISION" in content
    assert "## Sub-Issues" in content
    assert "### #101 — Sub task 1" in content


@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
def test_compose_aaa_normalizes_headers(mock_tl):
    issue = {
        "number": 300,
        "title": "Issue with paren headers",
        "state": "open",
        "body": "## ARCHITECTURE (Issue TRUG)\nsome detail",
        "updated_at": "2026-02-20T00:00:00Z",
    }
    content = _compose_aaa("TRUGS_TOOLS", issue, [], "X", "Y")
    assert "## ARCHITECTURE\n" in content
    assert "(Issue TRUG)" not in content


@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
def test_compose_aaa_no_sub_issues(mock_tl):
    issue = {
        "number": 200,
        "title": "Empty issue",
        "state": "open",
        "body": "No sub-issues yet.",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    content = _compose_aaa("TRUGS_EMPTY", issue, [], "X", "Y")
    assert "## Sub-Issues" in content
    assert "## Recent Activity" not in content


# ---------------------------------------------------------------------------
# _write_aaa / _archive_aaa
# ---------------------------------------------------------------------------


def test_write_aaa_creates_file(tmp_path):
    folder = tmp_path / "MY_FOLDER"
    _write_aaa(folder, "# MY_FOLDER/\n\nContent here.\n")
    aaa = folder / "AAA.md"
    assert aaa.exists()
    assert "Content here." in aaa.read_text()


def test_archive_aaa_renames(tmp_path):
    folder = tmp_path / "MY_FOLDER"
    folder.mkdir()
    (folder / "AAA.md").write_text("Old content", encoding="utf-8")
    _archive_aaa(folder, "My old issue title")
    assert not (folder / "AAA.md").exists()
    archived = list(folder.glob("ZZZ_AAA_*.md"))
    assert len(archived) == 1


def test_archive_aaa_noop_when_no_aaa(tmp_path):
    folder = tmp_path / "MY_FOLDER"
    folder.mkdir()
    _archive_aaa(folder, "some title")  # Should not raise


# ---------------------------------------------------------------------------
# generate_all — end-to-end with mocked API
# ---------------------------------------------------------------------------


def _make_issue(number, title, body="", created_at="2026-01-01T00:00:00Z"):
    return {
        "number": number,
        "title": title,
        "state": "open",
        "body": body,
        "updated_at": "2026-02-25T00:00:00Z",
        "created_at": created_at,
    }


def _make_closed_issue(number, title):
    return {
        "number": number,
        "title": title,
        "state": "closed",
        "body": "",
        "updated_at": "2026-01-01T00:00:00Z",
        "created_at": "2025-12-01T00:00:00Z",
    }


@patch("trugs_tools.aaa_generator._detect_owner_repo", return_value=("X", "Y"))
@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
@patch("trugs_tools.aaa_generator._sub_issues", return_value=[])
@patch("trugs_tools.aaa_generator._issues_for_label")
@patch("trugs_tools.aaa_generator._list_folder_labels")
def test_generate_all_writes_aaa(mock_labels, mock_issues, mock_subs, mock_tl, mock_detect, tmp_path):
    mock_labels.return_value = ["folder:TRUGS_TOOLS"]
    mock_issues.return_value = [_make_issue(500, "Build TRUGS_TOOLS")]
    folder = tmp_path / "TRUGS_TOOLS"
    folder.mkdir()
    generate_all(str(tmp_path), token="fake")
    aaa = folder / "AAA.md"
    assert aaa.exists()
    assert "# TRUGS_TOOLS/" in aaa.read_text()


@patch("trugs_tools.aaa_generator._detect_owner_repo", return_value=("X", "Y"))
@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
@patch("trugs_tools.aaa_generator._sub_issues", return_value=[])
@patch("trugs_tools.aaa_generator._api_get")
@patch("trugs_tools.aaa_generator._issues_for_label")
@patch("trugs_tools.aaa_generator._list_folder_labels")
def test_generate_all_archives_when_closed(mock_labels, mock_issues, mock_api, mock_subs, mock_tl, mock_detect, tmp_path):
    mock_labels.return_value = ["folder:OLD_FOLDER"]
    mock_issues.return_value = []  # No open issues
    mock_api.return_value = [_make_closed_issue(300, "Old completed work")]
    folder = tmp_path / "OLD_FOLDER"
    folder.mkdir()
    (folder / "AAA.md").write_text("Old content", encoding="utf-8")
    generate_all(str(tmp_path), token="fake")
    assert not (folder / "AAA.md").exists()
    archived = list(folder.glob("ZZZ_AAA_*.md"))
    assert len(archived) == 1


@patch("trugs_tools.aaa_generator._detect_owner_repo", return_value=("X", "Y"))
@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
@patch("trugs_tools.aaa_generator._sub_issues", return_value=[])
@patch("trugs_tools.aaa_generator._api_get", return_value=[])
@patch("trugs_tools.aaa_generator._issues_for_label", return_value=[])
@patch("trugs_tools.aaa_generator._list_folder_labels")
def test_generate_all_no_issue_leaves_existing_aaa(mock_labels, mock_issues, mock_api, mock_subs, mock_tl, mock_detect, tmp_path):
    """When there's no open or closed issue, leave existing AAA.md alone."""
    mock_labels.return_value = ["folder:LEGACY"]
    folder = tmp_path / "LEGACY"
    folder.mkdir()
    (folder / "AAA.md").write_text("Legacy hand-authored content", encoding="utf-8")
    generate_all(str(tmp_path), token="fake")
    assert (folder / "AAA.md").exists()
    assert "Legacy" in (folder / "AAA.md").read_text()


@patch("trugs_tools.aaa_generator._detect_owner_repo", return_value=("X", "Y"))
@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
@patch("trugs_tools.aaa_generator._sub_issues")
@patch("trugs_tools.aaa_generator._issues_for_label")
@patch("trugs_tools.aaa_generator._list_folder_labels")
def test_generate_all_includes_sub_issues(mock_labels, mock_issues, mock_subs, mock_tl, mock_detect, tmp_path):
    mock_labels.return_value = ["folder:TRUGS_AAA"]
    mock_issues.return_value = [_make_issue(600, "Parent issue", "## VISION\nParent body.")]
    mock_subs.return_value = [
        {"number": 601, "title": "Sub task A", "state": "closed", "body": "Sub A body", "created_at": "2026-02-01T00:00:00Z"},
        {"number": 602, "title": "Sub task B", "state": "open", "body": "Sub B body", "created_at": "2026-02-05T00:00:00Z"},
    ]
    folder = tmp_path / "TRUGS_AAA"
    folder.mkdir()
    generate_all(str(tmp_path), token="fake")
    content = (folder / "AAA.md").read_text()
    assert "### #601 — Sub task A" in content
    assert "### #602 — Sub task B" in content


@patch("trugs_tools.aaa_generator._detect_owner_repo", return_value=("X", "Y"))
@patch("trugs_tools.aaa_generator._timeline_events", return_value=[])
@patch("trugs_tools.aaa_generator._sub_issues", return_value=[])
@patch("trugs_tools.aaa_generator._issues_for_label")
@patch("trugs_tools.aaa_generator._list_folder_labels")
def test_generate_all_sorts_multiple_issues_by_created(mock_labels, mock_issues, mock_subs, mock_tl, mock_detect, tmp_path, capsys):
    """Uses the most recently created issue; warns about others."""
    mock_labels.return_value = ["folder:TRUGS_TOOLS"]
    older = _make_issue(10, "Older issue", created_at="2026-01-01T00:00:00Z")
    newer = _make_issue(20, "Newer issue", created_at="2026-02-01T00:00:00Z")
    # API returns older first (simulating unsorted response)
    mock_issues.return_value = [older, newer]
    folder = tmp_path / "TRUGS_TOOLS"
    folder.mkdir()
    generate_all(str(tmp_path), token="fake")
    out = capsys.readouterr().out
    # Newer issue (20) should be selected, older (10) warned about
    assert "WARNING" in out
    assert "#20" in (folder / "AAA.md").read_text()


@patch("trugs_tools.aaa_generator._detect_owner_repo", return_value=("X", "Y"))
@patch("trugs_tools.aaa_generator._list_folder_labels")
def test_generate_all_skips_nested_folder_name(mock_labels, mock_detect, tmp_path, capsys):
    """Folder names with '/' are skipped with a warning."""
    mock_labels.return_value = ["folder:PERAGO/nested"]
    generate_all(str(tmp_path), token="fake")
    assert "WARNING" in capsys.readouterr().out


@patch("trugs_tools.aaa_generator._detect_owner_repo", return_value=("X", "Y"))
@patch("trugs_tools.aaa_generator._list_folder_labels")
def test_generate_all_skips_empty_folder_name(mock_labels, mock_detect, tmp_path):
    """Empty folder name (from label 'folder:') is silently skipped."""
    mock_labels.return_value = ["folder:"]
    # Should not raise or write anything
    generate_all(str(tmp_path), token="fake")
    assert not (tmp_path / "AAA.md").exists()


@patch("trugs_tools.aaa_generator._detect_owner_repo", return_value=("X", "Y"))
@patch("trugs_tools.aaa_generator._list_folder_labels")
def test_generate_all_skips_dot_folder_name(mock_labels, mock_detect, tmp_path):
    """Folder name '.' is silently skipped to protect root AAA.md."""
    mock_labels.return_value = ["folder:."]
    generate_all(str(tmp_path), token="fake")
    assert not (tmp_path / "AAA.md").exists()


# ---------------------------------------------------------------------------
# CLI command wrapper
# ---------------------------------------------------------------------------


@patch("trugs_tools.aaa_generator.generate_all")
def test_aaa_generate_command_success(mock_gen, tmp_path):
    from trugs_tools.cli import aaa_generate_command
    exit_code = aaa_generate_command(["--root", str(tmp_path)])
    assert exit_code == 0
    mock_gen.assert_called_once_with(str(tmp_path))


@patch("trugs_tools.aaa_generator.generate_all", side_effect=RuntimeError("API error"))
def test_aaa_generate_command_error(mock_gen, tmp_path, capsys):
    from trugs_tools.cli import aaa_generate_command
    exit_code = aaa_generate_command(["--root", str(tmp_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "API error" in captured.err
    assert "generating AAA.md" in captured.err


def test_main_dispatcher_has_aaa_generate():
    """The main() dispatcher must register 'aaa-generate' subcommand."""
    import inspect
    from trugs_tools import cli as cli_module
    src = inspect.getsource(cli_module.main)
    assert "aaa-generate" in src
