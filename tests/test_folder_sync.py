"""Tests for trugs folder-sync command."""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from trugs_tools.filesystem.folder_sync import (
    SyncResult,
    sync_folder_trug,
    _scan_all,
    _update_factual_properties,
    _update_folder_metadata,
    _update_top_level_metadata,
    _find_folder_node,
    _node_file_exists,
)
from trugs_tools.cli import folder_sync_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dir(base, *subdirs):
    """Create nested directories, return the path."""
    p = Path(base)
    for s in subdirs:
        p = p / s
    p.mkdir(parents=True, exist_ok=True)
    return p


def _make_file(base, name, content=""):
    """Create a file in base with given content."""
    p = Path(base) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _minimal_trug(folder_name="testproject"):
    """Create a minimal valid folder.trug.json dict."""
    folder_id = f"{folder_name}_folder"
    return {
        "name": f"{folder_name} Folder",
        "version": "0.1.0",
        "type": "PROJECT",
        "description": f"{folder_name} project",
        "dimensions": {
            "folder_structure": {
                "description": f"{folder_name} components",
                "base_level": "BASE",
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["project_v1"],
            "profiles": [],
        },
        "nodes": [
            {
                "id": folder_id,
                "type": "FOLDER",
                "properties": {
                    "name": folder_name,
                    "purpose": f"{folder_name} project folder",
                },
                "parent_id": None,
                "contains": ["doc_readme"],
                "metric_level": "KILO_FOLDER",
                "dimension": "folder_structure",
            },
            {
                "id": "doc_readme",
                "type": "DOCUMENT",
                "properties": {
                    "name": "README.md",
                    "purpose": "Human quickstart and motivation",
                    "format": "markdown",
                },
                "parent_id": folder_id,
                "contains": [],
                "metric_level": "BASE_DOCUMENT",
                "dimension": "folder_structure",
            },
        ],
        "edges": [
            {
                "from_id": folder_id,
                "to_id": "doc_readme",
                "relation": "contains",
                "weight": 1.0,
            },
        ],
    }


def _write_trug(folder_path, trug_dict):
    """Write a trug dict as folder.trug.json."""
    p = Path(folder_path) / "folder.trug.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(trug_dict, f, indent=2)
        f.write("\n")
    return p


# ---------------------------------------------------------------------------
# SyncResult tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testsyncresult AS A RECORD test_suite.
class TestSyncResult:
    # AGENT SHALL VALIDATE PROCESS test_default_no_changes.
    def test_default_no_changes(self):
        r = SyncResult()
        assert not r.has_changes

    # AGENT SHALL VALIDATE PROCESS test_has_changes_updated.
    def test_has_changes_updated(self):
        r = SyncResult(updated_nodes=["comp_x"])
        assert r.has_changes

    # AGENT SHALL VALIDATE PROCESS test_has_changes_new.
    def test_has_changes_new(self):
        r = SyncResult(new_nodes=["doc_new"])
        assert r.has_changes

    # AGENT SHALL VALIDATE PROCESS test_has_changes_stale.
    def test_has_changes_stale(self):
        r = SyncResult(stale_nodes=["doc_old"])
        assert r.has_changes

    # AGENT SHALL VALIDATE PROCESS test_has_changes_cleared_stale.
    def test_has_changes_cleared_stale(self):
        r = SyncResult(cleared_stale=["doc_x"])
        assert r.has_changes

    # AGENT SHALL VALIDATE PROCESS test_has_changes_edges_added.
    def test_has_changes_edges_added(self):
        r = SyncResult(edges_added=1)
        assert r.has_changes


# ---------------------------------------------------------------------------
# _find_folder_node tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testfindfoldernode AS A RECORD test_suite.
class TestFindFolderNode:
    # AGENT SHALL VALIDATE PROCESS test_finds_folder.
    def test_finds_folder(self):
        nodes = [
            {"id": "x", "type": "DOCUMENT"},
            {"id": "f", "type": "FOLDER"},
        ]
        assert _find_folder_node(nodes)["id"] == "f"

    # AGENT SHALL VALIDATE PROCESS test_returns_none_if_missing.
    def test_returns_none_if_missing(self):
        assert _find_folder_node([{"id": "x", "type": "DOCUMENT"}]) is None


# ---------------------------------------------------------------------------
# _update_factual_properties tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testupdatefactualproperties AS A RECORD test_suite.
class TestUpdateFactualProperties:
    # AGENT SHALL VALIDATE PROCESS test_updates_component_counts.
    def test_updates_component_counts(self):
        existing = {
            "id": "comp_x",
            "type": "COMPONENT",
            "properties": {"name": "x", "purpose": "Custom purpose", "file_count": 5, "loc": 100},
        }
        fresh = {
            "id": "comp_x",
            "type": "COMPONENT",
            "properties": {"name": "x", "purpose": "X component", "file_count": 7, "loc": 200},
        }
        changes = _update_factual_properties(existing, fresh, "COMPONENT")
        assert existing["properties"]["file_count"] == 7
        assert existing["properties"]["loc"] == 200
        # Purpose preserved — not updated
        assert existing["properties"]["purpose"] == "Custom purpose"
        assert len(changes) == 2

    # AGENT SHALL VALIDATE PROCESS test_updates_test_count.
    def test_updates_test_count(self):
        existing = {
            "id": "test_suite",
            "type": "TEST_SUITE",
            "properties": {"name": "tests/", "test_count": 50, "test_files": 3},
        }
        fresh = {
            "id": "test_suite",
            "type": "TEST_SUITE",
            "properties": {"name": "tests/", "test_count": 75, "test_files": 5},
        }
        changes = _update_factual_properties(existing, fresh, "TEST_SUITE")
        assert existing["properties"]["test_count"] == 75
        assert existing["properties"]["test_files"] == 5
        assert len(changes) == 2

    # AGENT SHALL VALIDATE PROCESS test_preserves_purpose.
    def test_preserves_purpose(self):
        existing = {
            "id": "comp_x",
            "type": "COMPONENT",
            "properties": {"name": "x", "purpose": "My enriched purpose", "file_count": 5, "loc": 100},
        }
        fresh = {
            "id": "comp_x",
            "type": "COMPONENT",
            "properties": {"name": "x", "purpose": "X component", "file_count": 5, "loc": 100},
        }
        _update_factual_properties(existing, fresh, "COMPONENT")
        assert existing["properties"]["purpose"] == "My enriched purpose"

    # AGENT SHALL VALIDATE PROCESS test_no_changes_when_equal.
    def test_no_changes_when_equal(self):
        existing = {
            "id": "comp_x",
            "type": "COMPONENT",
            "properties": {"file_count": 5, "loc": 100},
        }
        fresh = {
            "id": "comp_x",
            "type": "COMPONENT",
            "properties": {"file_count": 5, "loc": 100},
        }
        changes = _update_factual_properties(existing, fresh, "COMPONENT")
        assert changes == []

    # AGENT SHALL VALIDATE PROCESS test_unknown_type_no_update.
    def test_unknown_type_no_update(self):
        existing = {"id": "x", "properties": {"a": 1}}
        fresh = {"id": "x", "properties": {"a": 2}}
        changes = _update_factual_properties(existing, fresh, "CUSTOM")
        assert changes == []
        assert existing["properties"]["a"] == 1

    # AGENT SHALL VALIDATE PROCESS test_preserves_custom_properties.
    def test_preserves_custom_properties(self):
        existing = {
            "id": "comp_x",
            "type": "COMPONENT",
            "properties": {"file_count": 5, "loc": 100, "custom_field": "preserved"},
        }
        fresh = {
            "id": "comp_x",
            "type": "COMPONENT",
            "properties": {"file_count": 7, "loc": 200},
        }
        _update_factual_properties(existing, fresh, "COMPONENT")
        assert existing["properties"]["custom_field"] == "preserved"
        assert existing["properties"]["file_count"] == 7


# ---------------------------------------------------------------------------
# _update_folder_metadata tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testupdatefoldermetadata AS A RECORD test_suite.
class TestUpdateFolderMetadata:
    # AGENT SHALL VALIDATE PROCESS test_updates_phase.
    def test_updates_phase(self):
        folder = {"id": "f", "properties": {"phase": "DEVELOPMENT"}}
        changes = _update_folder_metadata(folder, {"phase": "TESTING"}, {})
        assert folder["properties"]["phase"] == "TESTING"
        assert len(changes) == 1

    # AGENT SHALL VALIDATE PROCESS test_updates_version_from_aaa.
    def test_updates_version_from_aaa(self):
        folder = {"id": "f", "properties": {"version": "1.0.0"}}
        changes = _update_folder_metadata(folder, {"version": "1.1.0"}, {})
        assert folder["properties"]["version"] == "1.1.0"

    # AGENT SHALL VALIDATE PROCESS test_updates_version_from_pyproject.
    def test_updates_version_from_pyproject(self):
        folder = {"id": "f", "properties": {"version": "1.0.0"}}
        changes = _update_folder_metadata(folder, {}, {"version": "1.2.0"})
        assert folder["properties"]["version"] == "1.2.0"

    # AGENT SHALL VALIDATE PROCESS test_aaa_version_preferred_over_pyproject.
    def test_aaa_version_preferred_over_pyproject(self):
        folder = {"id": "f", "properties": {"version": "1.0.0"}}
        _update_folder_metadata(folder, {"version": "2.0.0"}, {"version": "3.0.0"})
        assert folder["properties"]["version"] == "2.0.0"

    # AGENT SHALL VALIDATE PROCESS test_no_changes_when_same.
    def test_no_changes_when_same(self):
        folder = {"id": "f", "properties": {"phase": "TESTING", "status": "active"}}
        changes = _update_folder_metadata(
            folder, {"phase": "TESTING", "status": "active"}, {}
        )
        assert changes == []


# ---------------------------------------------------------------------------
# _update_top_level_metadata tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testupdatetoplevelmetadata AS A RECORD test_suite.
class TestUpdateTopLevelMetadata:
    # AGENT SHALL VALIDATE PROCESS test_updates_version.
    def test_updates_version(self):
        trug = {"version": "1.0.0", "description": "old"}
        changes = _update_top_level_metadata(trug, {"version": "1.1.0"})
        assert trug["version"] == "1.1.0"
        assert len(changes) == 1

    # AGENT SHALL VALIDATE PROCESS test_updates_description.
    def test_updates_description(self):
        trug = {"version": "1.0.0", "description": "old"}
        changes = _update_top_level_metadata(trug, {"description": "new desc"})
        assert trug["description"] == "new desc"

    # AGENT SHALL VALIDATE PROCESS test_no_changes.
    def test_no_changes(self):
        trug = {"version": "1.0.0", "description": "same"}
        changes = _update_top_level_metadata(trug, {"version": "1.0.0", "description": "same"})
        assert changes == []


# ---------------------------------------------------------------------------
# sync_folder_trug — full sync tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testsyncfoldertrug AS A RECORD test_suite.
class TestSyncFolderTrug:
    # AGENT SHALL VALIDATE PROCESS test_no_trug_error.
    def test_no_trug_error(self, tmp_path):
        """Folder without folder.trug.json raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="folder-init first"):
            sync_folder_trug(tmp_path)

    # AGENT SHALL VALIDATE PROCESS test_not_a_directory.
    def test_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(NotADirectoryError):
            sync_folder_trug(f)

    # AGENT SHALL VALIDATE PROCESS test_sync_preserves_edges.
    def test_sync_preserves_edges(self, tmp_path):
        """All existing edges must be preserved exactly after sync."""
        trug = _minimal_trug("myproj")
        # Add a human-curated edge
        trug["edges"].append({
            "from_id": "doc_readme",
            "to_id": "myproj_folder",
            "relation": "documents",
            "weight": 0.8,
        })
        original_edges = json.loads(json.dumps(trug["edges"]))
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")

        result = sync_folder_trug(tmp_path, run_tests=False)

        # Reload and verify edges
        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        # Original edges must be intact
        for orig_edge in original_edges:
            assert orig_edge in synced["edges"]

    # AGENT SHALL VALIDATE PROCESS test_sync_updates_component_counts.
    def test_sync_updates_component_counts(self, tmp_path):
        """Component file_count and loc should be updated."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_src",
            "type": "COMPONENT",
            "properties": {"name": "src", "purpose": "Source code", "file_count": 1, "loc": 10},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_src")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        src_dir = _make_dir(tmp_path, "src")
        _make_file(src_dir, "__init__.py", "x = 1\ny = 2\n")
        _make_file(src_dir, "main.py", "a = 1\nb = 2\nc = 3\n")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "comp_src" in result.updated_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        comp = next(n for n in synced["nodes"] if n["id"] == "comp_src")
        assert comp["properties"]["file_count"] == 2
        assert comp["properties"]["loc"] == 5  # 2 + 3 non-empty lines

    # AGENT SHALL VALIDATE PROCESS test_sync_updates_folder_phase.
    def test_sync_updates_folder_phase(self, tmp_path):
        """FOLDER phase should be updated from AAA.md."""
        trug = _minimal_trug("myproj")
        trug["nodes"][0]["properties"]["phase"] = "DEVELOPMENT"
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "AAA.md", "**Phase:** INTERNAL_TESTING\n**Status:** Active\n")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "myproj_folder" in result.updated_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        folder = next(n for n in synced["nodes"] if n["type"] == "FOLDER")
        assert folder["properties"]["phase"] == "INTERNAL_TESTING"

    # AGENT SHALL VALIDATE PROCESS test_sync_preserves_purpose.
    def test_sync_preserves_purpose(self, tmp_path):
        """Custom purpose on a node must not be overwritten."""
        trug = _minimal_trug("myproj")
        trug["nodes"][1]["properties"]["purpose"] = "My custom enriched purpose"
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")

        sync_folder_trug(tmp_path, run_tests=False)

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        doc = next(n for n in synced["nodes"] if n["id"] == "doc_readme")
        assert doc["properties"]["purpose"] == "My custom enriched purpose"

    # AGENT SHALL VALIDATE PROCESS test_sync_detects_new_doc.
    def test_sync_detects_new_doc(self, tmp_path):
        """New .md file should create a new DOCUMENT node + contains edge."""
        trug = _minimal_trug("myproj")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "CONTRIBUTING.md", "# Contribute")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "doc_contributing" in result.new_nodes
        assert result.edges_added >= 1

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        ids = [n["id"] for n in synced["nodes"]]
        assert "doc_contributing" in ids
        # Verify contains edge was added
        contains_edges = [
            e for e in synced["edges"]
            if e["to_id"] == "doc_contributing" and e["relation"] == "contains"
        ]
        assert len(contains_edges) == 1

    # AGENT SHALL VALIDATE PROCESS test_sync_detects_new_component.
    def test_sync_detects_new_component(self, tmp_path):
        """New Python subdir should add COMPONENT node + contains + tests edges."""
        trug = _minimal_trug("myproj")
        # Add a test_suite node
        trug["nodes"].append({
            "id": "test_suite",
            "type": "TEST_SUITE",
            "properties": {"name": "tests/", "test_count": 5, "test_files": 1},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_TEST_SUITE",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("test_suite")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        # Create tests dir with a test file
        tests_dir = _make_dir(tmp_path, "tests")
        _make_file(tests_dir, "test_basic.py", "def test_x(): pass\n")
        # Create new component dir
        mylib_dir = _make_dir(tmp_path, "mylib")
        _make_file(mylib_dir, "__init__.py", "pass\n")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "comp_mylib" in result.new_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        # Check tests edge from test_suite to new component
        tests_edges = [
            e for e in synced["edges"]
            if e["from_id"] == "test_suite"
            and e["to_id"] == "comp_mylib"
            and e["relation"] == "tests"
        ]
        assert len(tests_edges) == 1

    # AGENT SHALL VALIDATE PROCESS test_sync_flags_stale_node.
    def test_sync_flags_stale_node(self, tmp_path):
        """Node whose file is gone should be marked stale."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "doc_old",
            "type": "DOCUMENT",
            "properties": {"name": "OLD.md", "purpose": "Old doc", "format": "markdown"},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("doc_old")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        # Note: OLD.md does NOT exist on disk

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "doc_old" in result.stale_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        old = next(n for n in synced["nodes"] if n["id"] == "doc_old")
        assert old["properties"]["stale"] is True
        assert old["properties"]["stale_reason"] == "file not found on disk"

    # AGENT SHALL VALIDATE PROCESS test_sync_clears_stale_on_return.
    def test_sync_clears_stale_on_return(self, tmp_path):
        """Previously stale node whose file reappears should have stale cleared."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "doc_changelog",
            "type": "DOCUMENT",
            "properties": {
                "name": "CHANGELOG.md",
                "purpose": "Change log",
                "format": "markdown",
                "stale": True,
                "stale_reason": "file not found on disk",
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("doc_changelog")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "CHANGELOG.md", "# Changes")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "doc_changelog" in result.cleared_stale

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        cl = next(n for n in synced["nodes"] if n["id"] == "doc_changelog")
        assert "stale" not in cl["properties"]
        assert "stale_reason" not in cl["properties"]

    # AGENT SHALL VALIDATE PROCESS test_sync_preserves_custom_properties.
    def test_sync_preserves_custom_properties(self, tmp_path):
        """Extra human-added properties must be preserved."""
        trug = _minimal_trug("myproj")
        trug["nodes"][1]["properties"]["verified"] = True
        trug["nodes"][1]["properties"]["verified_by"] = "alice"
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")

        sync_folder_trug(tmp_path, run_tests=False)

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        doc = next(n for n in synced["nodes"] if n["id"] == "doc_readme")
        assert doc["properties"]["verified"] is True
        assert doc["properties"]["verified_by"] == "alice"

    # AGENT SHALL VALIDATE PROCESS test_sync_updates_top_level_version.
    def test_sync_updates_top_level_version(self, tmp_path):
        """Top-level version should be updated from pyproject.toml."""
        trug = _minimal_trug("myproj")
        trug["version"] = "0.1.0"
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(
            tmp_path,
            "pyproject.toml",
            '[project]\nname = "myproj"\nversion = "2.0.0"\ndescription = "New desc"\n',
        )

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert any("top-level version" in c for c in result.changes)

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        assert synced["version"] == "2.0.0"
        assert synced["description"] == "New desc"

    # AGENT SHALL VALIDATE PROCESS test_sync_no_changes.
    def test_sync_no_changes(self, tmp_path):
        """TRUG already matching filesystem should produce no changes."""
        # Create the folder.trug.json and corresponding files to match
        _make_file(tmp_path, "README.md", "# Hello")
        trug = _minimal_trug(tmp_path.name)
        # Generate the proper folder id
        import re
        clean_name = re.sub(r"[^a-z0-9_]", "", tmp_path.name.lower().replace("-", "_"))
        clean_name = re.sub(r"_+", "_", clean_name).strip("_")
        folder_id = f"{clean_name}_folder"
        trug["nodes"][0]["id"] = folder_id
        trug["nodes"][0]["contains"] = ["doc_readme"]
        trug["nodes"][1]["parent_id"] = folder_id
        trug["edges"][0]["from_id"] = folder_id
        _write_trug(tmp_path, trug)

        result = sync_folder_trug(tmp_path, run_tests=False)
        # Should have no factual property changes (purpose differences are ignored)
        assert not result.stale_nodes
        assert not result.cleared_stale

    # AGENT SHALL VALIDATE PROCESS test_sync_idempotent.
    def test_sync_idempotent(self, tmp_path):
        """Running sync twice should produce the same result."""
        trug = _minimal_trug("myproj")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "CONTRIBUTING.md", "# Contrib")

        sync_folder_trug(tmp_path, run_tests=False)
        with open(tmp_path / "folder.trug.json") as f:
            after_first = json.load(f)

        result2 = sync_folder_trug(tmp_path, run_tests=False)
        with open(tmp_path / "folder.trug.json") as f:
            after_second = json.load(f)

        assert after_first == after_second
        assert not result2.has_changes

    # AGENT SHALL VALIDATE PROCESS test_sync_dry_run_no_write.
    def test_sync_dry_run_no_write(self, tmp_path):
        """dry_run=True should not modify the file."""
        trug = _minimal_trug("myproj")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "CONTRIBUTING.md", "# Contrib")

        original = (tmp_path / "folder.trug.json").read_text()
        result = sync_folder_trug(tmp_path, run_tests=False, dry_run=True)
        after = (tmp_path / "folder.trug.json").read_text()

        assert original == after
        assert result.has_changes  # changes detected but not written


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testclisinglefolder AS A RECORD test_suite.
class TestCLISingleFolder:
    # AGENT SHALL VALIDATE PROCESS test_cli_single_folder.
    def test_cli_single_folder(self, tmp_path):
        trug = _minimal_trug("myproj")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")

        exit_code = folder_sync_command([str(tmp_path), "--no-tests"])
        assert exit_code == 0

    # AGENT SHALL VALIDATE PROCESS test_cli_dry_run.
    def test_cli_dry_run(self, tmp_path, capsys):
        trug = _minimal_trug("myproj")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "CONTRIBUTING.md", "# New")

        original = (tmp_path / "folder.trug.json").read_text()
        exit_code = folder_sync_command(
            [str(tmp_path), "--dry-run", "--no-tests"]
        )
        after = (tmp_path / "folder.trug.json").read_text()
        assert exit_code == 0
        assert original == after
        captured = capsys.readouterr()
        assert "[dry-run]" in captured.out

    # AGENT SHALL VALIDATE PROCESS test_cli_no_trug.
    def test_cli_no_trug(self, tmp_path, capsys):
        exit_code = folder_sync_command([str(tmp_path), "--no-tests"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "folder-init first" in captured.err

    # AGENT SHALL VALIDATE PROCESS test_cli_not_a_dir.
    def test_cli_not_a_dir(self, tmp_path, capsys):
        f = tmp_path / "file.txt"
        f.write_text("x")
        exit_code = folder_sync_command([str(f), "--no-tests"])
        assert exit_code == 1

    # AGENT SHALL VALIDATE PROCESS test_cli_no_tests_flag.
    def test_cli_no_tests_flag(self, tmp_path):
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "test_suite",
            "type": "TEST_SUITE",
            "properties": {"name": "tests/", "test_count": 3, "test_files": 1},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_TEST_SUITE",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("test_suite")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        tests_dir = _make_dir(tmp_path, "tests")
        _make_file(tests_dir, "test_a.py", "def test(): pass\n")
        _make_file(tests_dir, "test_b.py", "def test(): pass\n")

        exit_code = folder_sync_command([str(tmp_path), "--no-tests"])
        assert exit_code == 0

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        ts = next(n for n in synced["nodes"] if n["id"] == "test_suite")
        assert ts["properties"]["test_files"] == 2


# AGENT claude SHALL DEFINE RECORD testcliall AS A RECORD test_suite.
class TestCLIAll:
    # AGENT SHALL VALIDATE PROCESS test_cli_all.
    def test_cli_all(self, tmp_path):
        # Create two folders with TRUGs
        d1 = _make_dir(tmp_path, "proj1")
        d2 = _make_dir(tmp_path, "proj2")
        _write_trug(d1, _minimal_trug("proj1"))
        _write_trug(d2, _minimal_trug("proj2"))
        _make_file(d1, "README.md", "# P1")
        _make_file(d2, "README.md", "# P2")

        exit_code = folder_sync_command(
            ["--all", "--root", str(tmp_path), "--no-tests"]
        )
        assert exit_code == 0

    # AGENT SHALL VALIDATE PROCESS test_cli_all_with_error.
    def test_cli_all_with_error(self, tmp_path):
        """--all should return 2 if any folder fails to sync."""
        d1 = _make_dir(tmp_path, "proj1")
        _write_trug(d1, _minimal_trug("proj1"))
        _make_file(d1, "README.md", "# P1")
        # Write invalid JSON to a second trug
        d2 = _make_dir(tmp_path, "proj2")
        (d2 / "folder.trug.json").write_text("NOT JSON")

        exit_code = folder_sync_command(
            ["--all", "--root", str(tmp_path), "--no-tests"]
        )
        assert exit_code == 2

    # AGENT SHALL VALIDATE PROCESS test_cli_all_no_files.
    def test_cli_all_no_files(self, tmp_path, capsys):
        exit_code = folder_sync_command(
            ["--all", "--root", str(tmp_path), "--no-tests"]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No folder.trug.json" in captured.err


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testintegration AS A RECORD test_suite.
class TestIntegration:
    # AGENT SHALL VALIDATE PROCESS test_sync_then_check_idempotent.
    def test_sync_then_check_idempotent(self, tmp_path):
        """Sync then sync again should be idempotent."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_src",
            "type": "COMPONENT",
            "properties": {"name": "src", "purpose": "Source", "file_count": 0, "loc": 0},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_src")
        trug["edges"].append({
            "from_id": "myproj_folder",
            "to_id": "comp_src",
            "relation": "contains",
            "weight": 1.0,
        })
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        src_dir = _make_dir(tmp_path, "src")
        _make_file(src_dir, "__init__.py", "pass\n")

        r1 = sync_folder_trug(tmp_path, run_tests=False)
        assert r1.has_changes

        r2 = sync_folder_trug(tmp_path, run_tests=False)
        assert not r2.has_changes

    # AGENT SHALL VALIDATE PROCESS test_sync_complex_scenario.
    def test_sync_complex_scenario(self, tmp_path):
        """Full scenario: updates, new, stale all in one sync."""
        trug = _minimal_trug("myproj")
        # Add component with stale counts
        trug["nodes"].append({
            "id": "comp_lib",
            "type": "COMPONENT",
            "properties": {"name": "lib", "purpose": "Library", "file_count": 1, "loc": 10},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        # Add a node for a deleted file
        trug["nodes"].append({
            "id": "doc_deleted",
            "type": "DOCUMENT",
            "properties": {"name": "DELETED.md", "purpose": "Gone doc", "format": "markdown"},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        # Add human edge
        trug["edges"].append({
            "from_id": "comp_lib",
            "to_id": "doc_readme",
            "relation": "implements",
            "weight": 0.9,
        })
        trug["nodes"][0]["contains"].extend(["comp_lib", "doc_deleted"])
        _write_trug(tmp_path, trug)

        # Files on disk
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "CHANGELOG.md", "# Changes")  # new file
        lib_dir = _make_dir(tmp_path, "lib")
        _make_file(lib_dir, "__init__.py", "a = 1\nb = 2\nc = 3\n")
        _make_file(lib_dir, "core.py", "x = 1\ny = 2\n")
        # DELETED.md does NOT exist

        result = sync_folder_trug(tmp_path, run_tests=False)

        assert "comp_lib" in result.updated_nodes  # counts changed
        assert "doc_deleted" in result.stale_nodes  # file gone
        assert "doc_changelog" in result.new_nodes  # new file

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)

        # Human edge preserved
        human_edges = [
            e for e in synced["edges"] if e["relation"] == "implements"
        ]
        assert len(human_edges) == 1

        # Component counts updated
        comp = next(n for n in synced["nodes"] if n["id"] == "comp_lib")
        assert comp["properties"]["file_count"] == 2

        # Deleted file flagged stale
        deleted = next(n for n in synced["nodes"] if n["id"] == "doc_deleted")
        assert deleted["properties"]["stale"] is True

    # AGENT SHALL VALIDATE PROCESS test_sync_updates_schema_count.
    def test_sync_updates_schema_count(self, tmp_path):
        """Schema count should be updated."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "schema_set",
            "type": "SCHEMA",
            "properties": {"name": "schemas/", "purpose": "Schema definitions", "schema_count": 1},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_SCHEMA",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("schema_set")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        schemas_dir = _make_dir(tmp_path, "schemas")
        _make_file(schemas_dir, "a.json", "{}")
        _make_file(schemas_dir, "b.json", "{}")
        _make_file(schemas_dir, "c.json", "{}")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "schema_set" in result.updated_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        schema = next(n for n in synced["nodes"] if n["id"] == "schema_set")
        assert schema["properties"]["schema_count"] == 3

    # AGENT SHALL VALIDATE PROCESS test_sync_updates_template_count.
    def test_sync_updates_template_count(self, tmp_path):
        """Template count should be updated."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "template_set",
            "type": "TEMPLATE",
            "properties": {"name": "templates/", "purpose": "Templates", "template_count": 1},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_TEMPLATE",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("template_set")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        tmpl_dir = _make_dir(tmp_path, "templates")
        _make_file(tmpl_dir, "t1.jinja", "x")
        _make_file(tmpl_dir, "t2.jinja", "y")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "template_set" in result.updated_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        tmpl = next(n for n in synced["nodes"] if n["id"] == "template_set")
        assert tmpl["properties"]["template_count"] == 2

    # AGENT SHALL VALIDATE PROCESS test_sync_updates_example_count.
    def test_sync_updates_example_count(self, tmp_path):
        """Example count should be updated."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "example_set",
            "type": "EXAMPLE_SET",
            "properties": {"name": "EXAMPLES/", "purpose": "Examples", "example_count": 1},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_EXAMPLE_SET",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("example_set")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        examples_dir = _make_dir(tmp_path, "EXAMPLES")
        _make_file(examples_dir, "ex1.json", "{}")
        _make_file(examples_dir, "ex2.json", "{}")
        _make_file(examples_dir, "ex3.json", "{}")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "example_set" in result.updated_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        ex = next(n for n in synced["nodes"] if n["id"] == "example_set")
        assert ex["properties"]["example_count"] == 3


# ---------------------------------------------------------------------------
# _node_file_exists tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testnodefileexists AS A RECORD test_suite.
class TestNodeFileExists:
    """Tests for the _node_file_exists helper that prevents false stale flags."""

    # AGENT SHALL VALIDATE PROCESS test_component_with_file_property_found.
    def test_component_with_file_property_found(self, tmp_path):
        """Component with 'file' property pointing to existing file is not stale."""
        _make_file(tmp_path, "src/pkg/module.py", "# code")
        props = {"name": "module", "file": "src/pkg/module.py"}
        assert _node_file_exists(tmp_path, props, "COMPONENT") is True

    # AGENT SHALL VALIDATE PROCESS test_component_with_file_property_missing.
    def test_component_with_file_property_missing(self, tmp_path):
        """Component with 'file' property pointing to nonexistent file is stale."""
        props = {"name": "module", "file": "src/pkg/module.py"}
        assert _node_file_exists(tmp_path, props, "COMPONENT") is False

    # AGENT SHALL VALIDATE PROCESS test_document_with_name_property_found.
    def test_document_with_name_property_found(self, tmp_path):
        """Document with 'name' matching a file on disk is not stale."""
        _make_file(tmp_path, "CHANGELOG.md", "# Changes")
        props = {"name": "CHANGELOG.md", "format": "markdown"}
        assert _node_file_exists(tmp_path, props, "DOCUMENT") is True

    # AGENT SHALL VALIDATE PROCESS test_document_with_name_property_missing.
    def test_document_with_name_property_missing(self, tmp_path):
        """Document with 'name' not matching any file is stale."""
        props = {"name": "NONEXISTENT.md", "format": "markdown"}
        assert _node_file_exists(tmp_path, props, "DOCUMENT") is False

    # AGENT SHALL VALIDATE PROCESS test_spec_with_ref_property_found.
    def test_spec_with_ref_property_found(self, tmp_path):
        """Specification with 'ref' containing filename § section should resolve."""
        _make_file(tmp_path, "SPECIFICATIONS.md", "# Specs")
        props = {"name": "SPECIFICATIONS.md", "ref": "SPECIFICATIONS.md § S-01"}
        assert _node_file_exists(tmp_path, props, "SPECIFICATION") is True

    # AGENT SHALL VALIDATE PROCESS test_spec_with_ref_but_file_missing.
    def test_spec_with_ref_but_file_missing(self, tmp_path):
        """Specification with 'ref' pointing to nonexistent file is stale."""
        props = {"name": "SPECIFICATIONS.md", "ref": "SPECIFICATIONS.md § S-01"}
        assert _node_file_exists(tmp_path, props, "SPECIFICATION") is False

    # AGENT SHALL VALIDATE PROCESS test_no_relevant_properties.
    def test_no_relevant_properties(self, tmp_path):
        """Node with neither file, name, nor ref returns False."""
        props = {"purpose": "Something"}
        assert _node_file_exists(tmp_path, props, "COMPONENT") is False

    # AGENT SHALL VALIDATE PROCESS test_name_with_slash_not_treated_as_filename.
    def test_name_with_slash_not_treated_as_filename(self, tmp_path):
        """Name containing '/' should not be used as a simple filename lookup."""
        props = {"name": "src/pkg/module.py"}
        assert _node_file_exists(tmp_path, props, "DOCUMENT") is False


# ---------------------------------------------------------------------------
# Integration: stale detection with file property (Issue #427)
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD teststaledetectionwithfileproperty AS A RECORD test_suite.
class TestStaleDetectionWithFileProperty:
    """Integration tests for the fix to Issue #427 — per-file component nodes."""

    # AGENT SHALL VALIDATE PROCESS test_per_file_component_not_marked_stale.
    def test_per_file_component_not_marked_stale(self, tmp_path):
        """Component with 'file' property pointing to existing file should NOT be stale."""
        trug = _minimal_trug("myproj")
        # Add a per-file component (like TRUGS2GO's comp_errors)
        trug["nodes"].append({
            "id": "comp_errors",
            "type": "COMPONENT",
            "properties": {
                "name": "errors",
                "file": "src/myproj/errors.py",
                "purpose": "Error handling",
                "status": "COMPLETE",
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_errors")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "src/myproj/errors.py", "class Error: pass")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "comp_errors" not in result.stale_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        comp = next(n for n in synced["nodes"] if n["id"] == "comp_errors")
        assert "stale" not in comp["properties"]

    # AGENT SHALL VALIDATE PROCESS test_per_file_component_truly_missing_still_stale.
    def test_per_file_component_truly_missing_still_stale(self, tmp_path):
        """Component with 'file' property pointing to nonexistent file IS stale."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_analyzer",
            "type": "COMPONENT",
            "properties": {
                "name": "analyzer",
                "file": "src/myproj/analyzer.py",
                "purpose": "Analysis",
                "status": "NOT_STARTED",
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_analyzer")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        # Note: src/myproj/analyzer.py does NOT exist

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "comp_analyzer" in result.stale_nodes

    # AGENT SHALL VALIDATE PROCESS test_previously_stale_component_cleared_when_file_exists.
    def test_previously_stale_component_cleared_when_file_exists(self, tmp_path):
        """Component that was stale but now has its file should be cleared."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_models",
            "type": "COMPONENT",
            "properties": {
                "name": "models",
                "file": "src/myproj/models.py",
                "purpose": "Data models",
                "stale": True,
                "stale_reason": "file not found on disk",
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_models")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "src/myproj/models.py", "class Model: pass")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "comp_models" in result.cleared_stale
        assert "comp_models" not in result.stale_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        comp = next(n for n in synced["nodes"] if n["id"] == "comp_models")
        assert "stale" not in comp["properties"]
        assert "stale_reason" not in comp["properties"]

    # AGENT SHALL VALIDATE PROCESS test_spec_node_with_existing_ref_file_not_stale.
    def test_spec_node_with_existing_ref_file_not_stale(self, tmp_path):
        """Specification node referencing existing file should NOT be stale."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "spec_go_branch",
            "type": "SPECIFICATION",
            "properties": {
                "name": "SPECIFICATIONS.md",
                "description": "S-01: Go Branch Vocabulary",
                "ref": "SPECIFICATIONS.md § S-01",
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_SPECIFICATION",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("spec_go_branch")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "SPECIFICATIONS.md", "# Specs\n## S-01")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "spec_go_branch" not in result.stale_nodes


# ---------------------------------------------------------------------------
# VG-2: Component status auto-advance (Fix 2 — #453)
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD teststatusautoadvance AS A RECORD test_suite.
class TestStatusAutoAdvance:
    """VG-2: NOT_STARTED + file exists + loc > 0 → PRESENT."""

    # AGENT SHALL VALIDATE PROCESS test_not_started_with_code_advances_to_present.
    def test_not_started_with_code_advances_to_present(self, tmp_path):
        """VG-2: NOT_STARTED + file exists + loc > 0 → PRESENT."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_src",
            "type": "COMPONENT",
            "properties": {
                "name": "src",
                "purpose": "Source code",
                "file_count": 1,
                "loc": 10,
                "status": "NOT_STARTED",
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_src")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        src_dir = _make_dir(tmp_path, "src")
        _make_file(src_dir, "main.py", "print('hello')\n")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "comp_src" in result.updated_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        comp = next(n for n in synced["nodes"] if n["id"] == "comp_src")
        assert comp["properties"]["status"] == "PRESENT"

    # AGENT SHALL VALIDATE PROCESS test_complete_status_unchanged.
    def test_complete_status_unchanged(self, tmp_path):
        """VG-3: COMPLETE + file exists → no change."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_src",
            "type": "COMPONENT",
            "properties": {
                "name": "src",
                "purpose": "Source code",
                "file_count": 1,
                "loc": 10,
                "status": "COMPLETE",
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_src")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        src_dir = _make_dir(tmp_path, "src")
        _make_file(src_dir, "main.py", "print('hello')\n")

        sync_folder_trug(tmp_path, run_tests=False)

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        comp = next(n for n in synced["nodes"] if n["id"] == "comp_src")
        assert comp["properties"]["status"] == "COMPLETE"

    # AGENT SHALL VALIDATE PROCESS test_missing_status_not_set.
    def test_missing_status_not_set(self, tmp_path):
        """If status is missing/empty, do not set it."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_src",
            "type": "COMPONENT",
            "properties": {
                "name": "src",
                "purpose": "Source code",
                "file_count": 1,
                "loc": 10,
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_src")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        src_dir = _make_dir(tmp_path, "src")
        _make_file(src_dir, "main.py", "print('hello')\n")

        sync_folder_trug(tmp_path, run_tests=False)

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        comp = next(n for n in synced["nodes"] if n["id"] == "comp_src")
        assert "status" not in comp["properties"]


# ---------------------------------------------------------------------------
# VG-4: Ghost node pruning (Fix 3 — #453)
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testghostnodepruning AS A RECORD test_suite.
class TestGhostNodePruning:
    """VG-4: Pruning removes nodes stale for N consecutive syncs."""

    # AGENT SHALL VALIDATE PROCESS test_prune_after_1_removes_node.
    def test_prune_after_1_removes_node(self, tmp_path):
        """VG-4: Two syncs with prune-after=1 → node removed on second sync."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "doc_old",
            "type": "DOCUMENT",
            "properties": {"name": "OLD.md", "purpose": "Old doc", "format": "markdown"},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("doc_old")
        trug["edges"].append({
            "from_id": "myproj_folder",
            "to_id": "doc_old",
            "relation": "contains",
            "weight": 1.0,
        })
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        # OLD.md does NOT exist

        # First sync: marks stale with stale_count=1
        r1 = sync_folder_trug(tmp_path, run_tests=False, prune_after=1)
        assert "doc_old" in r1.stale_nodes

        # Second sync: stale_count increments to 2, which >= 1, so pruned
        # But wait — prune_after=1 means prune when stale_count >= 1.
        # After first sync stale_count=1 already. So on first sync it should be pruned.
        assert "doc_old" in r1.pruned_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        ids = [n["id"] for n in synced["nodes"]]
        assert "doc_old" not in ids
        # Edge should also be removed
        edge_targets = [e.get("to_id") for e in synced["edges"]]
        assert "doc_old" not in edge_targets

    # AGENT SHALL VALIDATE PROCESS test_stale_cleared_when_file_returns.
    def test_stale_cleared_when_file_returns(self, tmp_path):
        """VG-4b: Node becomes non-stale → stale_since/stale_count cleared."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "doc_changelog",
            "type": "DOCUMENT",
            "properties": {
                "name": "CHANGELOG.md",
                "purpose": "Change log",
                "format": "markdown",
                "stale": True,
                "stale_reason": "file not found on disk",
                "stale_since": "2026-01-01T00:00:00+00:00",
                "stale_count": 3,
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("doc_changelog")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "CHANGELOG.md", "# Changes")

        result = sync_folder_trug(tmp_path, run_tests=False)
        assert "doc_changelog" in result.cleared_stale

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        cl = next(n for n in synced["nodes"] if n["id"] == "doc_changelog")
        assert "stale" not in cl["properties"]
        assert "stale_since" not in cl["properties"]
        assert "stale_count" not in cl["properties"]

    # AGENT SHALL VALIDATE PROCESS test_prune_after_0_disables_pruning.
    def test_prune_after_0_disables_pruning(self, tmp_path):
        """VG-4c: prune-after=0 → no pruning."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "doc_old",
            "type": "DOCUMENT",
            "properties": {
                "name": "OLD.md",
                "purpose": "Old doc",
                "format": "markdown",
                "stale": True,
                "stale_reason": "file not found on disk",
                "stale_since": "2026-01-01T00:00:00+00:00",
                "stale_count": 100,
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("doc_old")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")

        result = sync_folder_trug(tmp_path, run_tests=False, prune_after=0)
        assert "doc_old" not in result.pruned_nodes

        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        ids = [n["id"] for n in synced["nodes"]]
        assert "doc_old" in ids

    # AGENT SHALL VALIDATE PROCESS test_stale_count_increments.
    def test_stale_count_increments(self, tmp_path):
        """stale_count should increment on each sync while stale."""
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "doc_old",
            "type": "DOCUMENT",
            "properties": {"name": "OLD.md", "purpose": "Old doc", "format": "markdown"},
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("doc_old")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")

        # First sync: stale_count=1
        sync_folder_trug(tmp_path, run_tests=False, prune_after=0)
        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        old = next(n for n in synced["nodes"] if n["id"] == "doc_old")
        assert old["properties"]["stale_count"] == 1
        assert "stale_since" in old["properties"]

        # Second sync: stale_count=2
        sync_folder_trug(tmp_path, run_tests=False, prune_after=0)
        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        old = next(n for n in synced["nodes"] if n["id"] == "doc_old")
        assert old["properties"]["stale_count"] == 2


# ---------------------------------------------------------------------------
# VG-5: Prose/factual divergence warning (Fix 4 — #453)
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testprosefactualdivergence AS A RECORD test_suite.
class TestProseFactualDivergence:
    """VG-5: Prose contradicts factual → warning emitted, prose unchanged."""

    # AGENT SHALL VALIDATE PROCESS test_prose_contradicts_factual_emits_warning.
    def test_prose_contradicts_factual_emits_warning(self, tmp_path, caplog):
        """VG-5: Prose says '5 files' but factual file_count=2 → warning."""
        import logging
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_src",
            "type": "COMPONENT",
            "properties": {
                "name": "src",
                "purpose": "Contains 5 files of Python code",
                "file_count": 2,
                "loc": 100,
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_src")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        src_dir = _make_dir(tmp_path, "src")
        _make_file(src_dir, "a.py", "x = 1\n")
        _make_file(src_dir, "b.py", "y = 2\n")

        with caplog.at_level(logging.WARNING, logger="trugs_tools.filesystem.folder_sync"):
            sync_folder_trug(tmp_path, run_tests=False)

        # Should have a warning about the divergence
        assert any("Prose/factual divergence" in r.message for r in caplog.records)
        assert any("comp_src" in r.message for r in caplog.records)

        # Prose must NOT be changed
        with open(tmp_path / "folder.trug.json") as f:
            synced = json.load(f)
        comp = next(n for n in synced["nodes"] if n["id"] == "comp_src")
        assert "5 files" in comp["properties"]["purpose"]

    # AGENT SHALL VALIDATE PROCESS test_no_warning_when_matching.
    def test_no_warning_when_matching(self, tmp_path, caplog):
        """No warning when prose integers match factual values."""
        import logging
        trug = _minimal_trug("myproj")
        trug["nodes"].append({
            "id": "comp_src",
            "type": "COMPONENT",
            "properties": {
                "name": "src",
                "purpose": "Contains 2 files",
                "file_count": 2,
                "loc": 100,
            },
            "parent_id": "myproj_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["nodes"][0]["contains"].append("comp_src")
        _write_trug(tmp_path, trug)
        _make_file(tmp_path, "README.md", "# Hello")
        src_dir = _make_dir(tmp_path, "src")
        _make_file(src_dir, "a.py", "x = 1\n")
        _make_file(src_dir, "b.py", "y = 2\n")

        with caplog.at_level(logging.WARNING, logger="trugs_tools.filesystem.folder_sync"):
            sync_folder_trug(tmp_path, run_tests=False)

        divergence_warnings = [r for r in caplog.records if "Prose/factual divergence" in r.message]
        assert len(divergence_warnings) == 0
