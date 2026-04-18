"""Tests for trugs folder-check command."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from trugs_tools.filesystem.folder_check import (
    REQUIRED_TOP_LEVEL_KEYS,
    VALID_CROSS_FOLDER_RELATIONS,
    VALID_INTERNAL_RELATIONS,
    VALID_NODE_TYPES,
    CheckResult,
    check_all,
    check_folder_trug,
    find_all_folder_trugs,
    format_json,
    format_text,
)
from trugs_tools.cli import folder_check_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_trug(**overrides):
    """Return a minimal valid folder.trug.json dict."""
    trug = {
        "name": "Test Folder",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": "test",
        "dimensions": {
            "folder_structure": {"description": "test", "base_level": "BASE"}
        },
        "capabilities": {"extensions": [], "vocabularies": [], "profiles": []},
        "nodes": [
            {
                "id": "test_folder",
                "type": "FOLDER",
                "properties": {"name": "test", "phase": "CODING", "status": "ok"},
                "parent_id": None,
                "contains": [],
                "metric_level": "KILO_FOLDER",
                "dimension": "folder_structure",
            }
        ],
        "edges": [],
    }
    trug.update(overrides)
    return trug


def _write_trug(tmpdir, trug_dict):
    """Write a folder.trug.json file and return its path."""
    path = Path(tmpdir) / "folder.trug.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trug_dict, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# Error-level checks (rules 1-11)
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testvalidjson AS A RECORD test_suite.
class TestValidJSON:
    """Rule 1: file must parse as valid JSON."""

    # AGENT SHALL VALIDATE PROCESS test_valid_json_passes.
    def test_valid_json_passes(self, tmp_path):
        p = _write_trug(tmp_path, _minimal_trug())
        r = check_folder_trug(p, check_filesystem=False)
        assert r.ok

    # AGENT SHALL VALIDATE PROCESS test_invalid_json_fails.
    def test_invalid_json_fails(self, tmp_path):
        p = tmp_path / "folder.trug.json"
        p.write_text("{bad json", encoding="utf-8")
        r = check_folder_trug(p, check_filesystem=False)
        assert not r.ok
        assert any("Invalid JSON" in e for e in r.errors)

    # AGENT SHALL VALIDATE PROCESS test_missing_file_fails.
    def test_missing_file_fails(self, tmp_path):
        p = tmp_path / "folder.trug.json"
        r = check_folder_trug(p, check_filesystem=False)
        assert not r.ok
        assert any("File not found" in e for e in r.errors)


# AGENT claude SHALL DEFINE RECORD testrequiredkeys AS A RECORD test_suite.
class TestRequiredKeys:
    """Rule 2: required top-level keys."""

    # AGENT SHALL VALIDATE PROCESS test_all_keys_present_passes.
    def test_all_keys_present_passes(self, tmp_path):
        p = _write_trug(tmp_path, _minimal_trug())
        r = check_folder_trug(p, check_filesystem=False)
        assert r.ok

    # AGENT SHALL VALIDATE PROCESS test_missing_key_fails.
    def test_missing_key_fails(self, tmp_path):
        trug = _minimal_trug()
        del trug["nodes"]
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert not r.ok
        assert any("Missing required top-level key: 'nodes'" in e for e in r.errors)


# AGENT claude SHALL DEFINE RECORD testfoldernodecount AS A RECORD test_suite.
class TestFolderNodeCount:
    """Rule 3: exactly 1 FOLDER node with parent_id=null."""

    # AGENT SHALL VALIDATE PROCESS test_one_folder_ok.
    def test_one_folder_ok(self, tmp_path):
        p = _write_trug(tmp_path, _minimal_trug())
        r = check_folder_trug(p, check_filesystem=False)
        assert r.ok

    # AGENT SHALL VALIDATE PROCESS test_no_folder_node.
    def test_no_folder_node(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"][0]["type"] = "DOCUMENT"
        trug["nodes"][0]["metric_level"] = "BASE_DOCUMENT"
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("No FOLDER node" in e for e in r.errors)

    # AGENT SHALL VALIDATE PROCESS test_multiple_folder_nodes.
    def test_multiple_folder_nodes(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "extra_folder",
            "type": "FOLDER",
            "properties": {"name": "extra"},
            "parent_id": None,
            "contains": [],
            "metric_level": "KILO_FOLDER",
            "dimension": "folder_structure",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("Multiple FOLDER nodes" in e for e in r.errors)


# AGENT claude SHALL DEFINE RECORD testvalidnodetypes AS A RECORD test_suite.
class TestValidNodeTypes:
    """Rule 4: only valid node types."""

    # AGENT SHALL VALIDATE PROCESS test_valid_types_pass.
    @pytest.mark.parametrize("ntype", sorted(VALID_NODE_TYPES.keys()))
    def test_valid_types_pass(self, tmp_path, ntype):
        trug = _minimal_trug()
        if ntype != "FOLDER":
            trug["nodes"].append({
                "id": f"test_{ntype.lower()}",
                "type": ntype,
                "properties": {"name": f"test_{ntype}"},
                "parent_id": "test_folder",
                "contains": [],
                "metric_level": VALID_NODE_TYPES[ntype],
                "dimension": "folder_structure",
            })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        invalid_type_errors = [e for e in r.errors if "invalid type" in e]
        assert len(invalid_type_errors) == 0

    # AGENT SHALL VALIDATE PROCESS test_invalid_type_fails.
    def test_invalid_type_fails(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "bad_node",
            "type": "GENERATED",
            "properties": {"name": "bad"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("invalid type 'GENERATED'" in e for e in r.errors)

    # AGENT SHALL VALIDATE PROCESS test_prose_node_passes.
    def test_prose_node_passes(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "prose_overview",
            "type": "PROSE",
            "properties": {"name": "overview", "zone": "overview", "file": "prose/overview.md"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert r.ok


# AGENT claude SHALL DEFINE RECORD testmetriclevels AS A RECORD test_suite.
class TestMetricLevels:
    """Rule 5: correct metric_level per type."""

    # AGENT SHALL VALIDATE PROCESS test_correct_levels_pass.
    def test_correct_levels_pass(self, tmp_path):
        trug = _minimal_trug()
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        metric_errors = [e for e in r.errors if "metric_level" in e]
        assert len(metric_errors) == 0

    # AGENT SHALL VALIDATE PROCESS test_wrong_level_fails.
    def test_wrong_level_fails(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"][0]["metric_level"] = "BASE_FOLDER"
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("metric_level 'BASE_FOLDER' should be 'KILO_FOLDER'" in e
                    for e in r.errors)


# AGENT claude SHALL DEFINE RECORD testedgerelations AS A RECORD test_suite.
class TestEdgeRelations:
    """Rules 6 & 7: valid internal and cross-folder edge relations."""

    # AGENT SHALL VALIDATE PROCESS test_valid_internal_relation.
    def test_valid_internal_relation(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "doc_readme",
            "type": "DOCUMENT",
            "properties": {"name": "README.md"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "doc_readme",
            "relation": "contains",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        rel_errors = [e for e in r.errors if "invalid internal relation" in e]
        assert len(rel_errors) == 0

    # AGENT SHALL VALIDATE PROCESS test_invalid_internal_relation.
    def test_invalid_internal_relation(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "doc_readme",
            "type": "DOCUMENT",
            "properties": {"name": "README.md"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "doc_readme",
            "relation": "EXTENDS",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("invalid internal relation 'EXTENDS'" in e for e in r.errors)

    # AGENT SHALL VALIDATE PROCESS test_valid_cross_folder_relation.
    def test_valid_cross_folder_relation(self, tmp_path):
        trug = _minimal_trug()
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "other_folder:some_node",
            "relation": "uses",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        cf_errors = [e for e in r.errors if "cross-folder" in e]
        assert len(cf_errors) == 0

    # AGENT SHALL VALIDATE PROCESS test_invalid_cross_folder_relation.
    def test_invalid_cross_folder_relation(self, tmp_path):
        trug = _minimal_trug()
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "other_folder:some_node",
            "relation": "contains",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("invalid cross-folder relation 'contains'" in e
                    for e in r.errors)


# AGENT claude SHALL DEFINE RECORD testcrossfoldersyntax AS A RECORD test_suite.
class TestCrossFolderSyntax:
    """Rule 8: cross-folder edge to_id must be folder_name:node_id."""

    # AGENT SHALL VALIDATE PROCESS test_valid_cross_folder_syntax.
    def test_valid_cross_folder_syntax(self, tmp_path):
        trug = _minimal_trug()
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "TRUGS_TOOLS:comp_validator",
            "relation": "uses",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        syntax_errors = [e for e in r.errors if "folder_name:node_id" in e]
        assert len(syntax_errors) == 0

    # AGENT SHALL VALIDATE PROCESS test_invalid_cross_folder_syntax_empty_parts.
    def test_invalid_cross_folder_syntax_empty_parts(self, tmp_path):
        trug = _minimal_trug()
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": ":node_only",
            "relation": "uses",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("folder_name:node_id" in e for e in r.errors)


# AGENT claude SHALL DEFINE RECORD testcontainsconsistency AS A RECORD test_suite.
class TestContainsConsistency:
    """Rule 9: contains-array consistency with contains edges."""

    # AGENT SHALL VALIDATE PROCESS test_consistent_contains.
    def test_consistent_contains(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"][0]["contains"] = ["doc_readme"]
        trug["nodes"].append({
            "id": "doc_readme",
            "type": "DOCUMENT",
            "properties": {"name": "README.md"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "doc_readme",
            "relation": "contains",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        consist_errors = [e for e in r.errors if "Contains-array" in e]
        assert len(consist_errors) == 0

    # AGENT SHALL VALIDATE PROCESS test_missing_contains_edge.
    def test_missing_contains_edge(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"][0]["contains"] = ["doc_readme"]
        trug["nodes"].append({
            "id": "doc_readme",
            "type": "DOCUMENT",
            "properties": {"name": "README.md"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        # No contains edge!
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("Contains-array lists 'doc_readme'" in e for e in r.errors)


# AGENT claude SHALL DEFINE RECORD testdanglingedges AS A RECORD test_suite.
class TestDanglingEdges:
    """Rule 10: no dangling edge references (internal)."""

    # AGENT SHALL VALIDATE PROCESS test_valid_edge_refs.
    def test_valid_edge_refs(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "comp_a",
            "type": "COMPONENT",
            "properties": {"name": "comp_a"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "comp_a",
            "relation": "contains",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        dangling = [e for e in r.errors if "does not reference any node" in e]
        assert len(dangling) == 0

    # AGENT SHALL VALIDATE PROCESS test_dangling_from_id.
    def test_dangling_from_id(self, tmp_path):
        trug = _minimal_trug()
        trug["edges"].append({
            "from_id": "ghost_node",
            "to_id": "test_folder",
            "relation": "describes",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("from_id 'ghost_node' does not reference" in e for e in r.errors)

    # AGENT SHALL VALIDATE PROCESS test_dangling_to_id.
    def test_dangling_to_id(self, tmp_path):
        trug = _minimal_trug()
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "missing_node",
            "relation": "contains",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("to_id 'missing_node' does not reference" in e for e in r.errors)

    # AGENT SHALL VALIDATE PROCESS test_cross_folder_to_id_not_dangling.
    def test_cross_folder_to_id_not_dangling(self, tmp_path):
        """Cross-folder to_ids should NOT be flagged as dangling."""
        trug = _minimal_trug()
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "OTHER:some_node",
            "relation": "uses",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        dangling = [e for e in r.errors if "does not reference any node" in e]
        assert len(dangling) == 0


# AGENT claude SHALL DEFINE RECORD testfilesystemexistence AS A RECORD test_suite.
class TestFilesystemExistence:
    """Rule 11: DOCUMENT/SPECIFICATION nodes reference existing files."""

    # AGENT SHALL VALIDATE PROCESS test_existing_file_passes.
    def test_existing_file_passes(self, tmp_path):
        (tmp_path / "README.md").write_text("# Hi", encoding="utf-8")
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "doc_readme",
            "type": "DOCUMENT",
            "properties": {"name": "README.md"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=True)
        fs_errors = [e for e in r.errors if "does not exist" in e]
        assert len(fs_errors) == 0

    # AGENT SHALL VALIDATE PROCESS test_missing_file_fails.
    def test_missing_file_fails(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "doc_readme",
            "type": "DOCUMENT",
            "properties": {"name": "README.md"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=True)
        assert any("does not exist" in e for e in r.errors)

    # AGENT SHALL VALIDATE PROCESS test_spec_file_missing.
    def test_spec_file_missing(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "spec_x",
            "type": "SPECIFICATION",
            "properties": {"name": "SPEC_X.md"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_SPECIFICATION",
            "dimension": "folder_structure",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=True)
        assert any("does not exist" in e for e in r.errors)


# ---------------------------------------------------------------------------
# Warning-level checks
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testwarnings AS A RECORD test_suite.
class TestWarnings:
    """Warning-level checks: on-disk items, stale flags, empty contains."""

    # AGENT SHALL VALIDATE PROCESS test_on_disk_not_in_trug.
    def test_on_disk_not_in_trug(self, tmp_path):
        (tmp_path / "orphan_file.md").write_text("orphan", encoding="utf-8")
        trug = _minimal_trug()
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=True)
        assert any("orphan_file.md" in w for w in r.warnings)

    # AGENT SHALL VALIDATE PROCESS test_stale_flag_warning.
    def test_stale_flag_warning(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"].append({
            "id": "doc_aaa",
            "type": "DOCUMENT",
            "properties": {"name": "AAA.md", "stale": True},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("stale=true" in w for w in r.warnings)

    # AGENT SHALL VALIDATE PROCESS test_empty_contains_warning.
    def test_empty_contains_warning(self, tmp_path):
        trug = _minimal_trug()
        # Default already has empty contains
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        assert any("empty contains" in w for w in r.warnings)

    # AGENT SHALL VALIDATE PROCESS test_non_empty_contains_no_warning.
    def test_non_empty_contains_no_warning(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"][0]["contains"] = ["comp_a"]
        trug["nodes"].append({
            "id": "comp_a",
            "type": "COMPONENT",
            "properties": {"name": "comp_a"},
            "parent_id": "test_folder",
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
        trug["edges"].append({
            "from_id": "test_folder",
            "to_id": "comp_a",
            "relation": "contains",
        })
        p = _write_trug(tmp_path, trug)
        r = check_folder_trug(p, check_filesystem=False)
        empty_warns = [w for w in r.warnings if "empty contains" in w]
        assert len(empty_warns) == 0


# ---------------------------------------------------------------------------
# Multi-file scanning
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testfindallfoldertrugs AS A RECORD test_suite.
class TestFindAllFolderTrugs:
    """find_all_folder_trugs discovers files correctly."""

    # AGENT SHALL VALIDATE PROCESS test_finds_files.
    def test_finds_files(self, tmp_path):
        sub1 = tmp_path / "A"
        sub1.mkdir()
        _write_trug(sub1, _minimal_trug())
        sub2 = tmp_path / "B"
        sub2.mkdir()
        _write_trug(sub2, _minimal_trug())
        found = find_all_folder_trugs(tmp_path)
        assert len(found) == 2

    # AGENT SHALL VALIDATE PROCESS test_excludes_zzz.
    def test_excludes_zzz(self, tmp_path):
        sub1 = tmp_path / "A"
        sub1.mkdir()
        _write_trug(sub1, _minimal_trug())
        zzz = tmp_path / "ZZZ_ARCHIVE"
        zzz.mkdir()
        _write_trug(zzz, _minimal_trug())
        found = find_all_folder_trugs(tmp_path)
        assert len(found) == 1
        assert "ZZZ_" not in str(found[0])


# AGENT claude SHALL DEFINE RECORD testcheckall AS A RECORD test_suite.
class TestCheckAll:
    """check_all wrapper logic."""

    # AGENT SHALL VALIDATE PROCESS test_scan_all.
    def test_scan_all(self, tmp_path):
        sub = tmp_path / "A"
        sub.mkdir()
        _write_trug(sub, _minimal_trug())
        results = check_all(scan_all=True, root=tmp_path, check_filesystem=False)
        assert len(results) == 1
        assert results[0].ok

    # AGENT SHALL VALIDATE PROCESS test_explicit_paths_file.
    def test_explicit_paths_file(self, tmp_path):
        p = _write_trug(tmp_path, _minimal_trug())
        results = check_all(paths=[str(p)], check_filesystem=False)
        assert len(results) == 1

    # AGENT SHALL VALIDATE PROCESS test_explicit_paths_dir.
    def test_explicit_paths_dir(self, tmp_path):
        _write_trug(tmp_path, _minimal_trug())
        results = check_all(paths=[str(tmp_path)], check_filesystem=False)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testformattext AS A RECORD test_suite.
class TestFormatText:
    """format_text produces readable output."""

    # AGENT SHALL VALIDATE PROCESS test_quiet_mode.
    def test_quiet_mode(self, tmp_path):
        p = _write_trug(tmp_path, _minimal_trug())
        r = check_folder_trug(p, check_filesystem=False)
        output = format_text([r], quiet=True)
        assert "0 error(s)" in output
        assert "1 file(s)" in output

    # AGENT SHALL VALIDATE PROCESS test_verbose_mode.
    def test_verbose_mode(self, tmp_path):
        p = _write_trug(tmp_path, _minimal_trug())
        r = check_folder_trug(p, check_filesystem=False)
        output = format_text([r], quiet=False)
        assert "Nodes:" in output
        assert "Edges:" in output


# AGENT claude SHALL DEFINE RECORD testformatjson AS A RECORD test_suite.
class TestFormatJSON:
    """format_json produces valid JSON."""

    # AGENT SHALL VALIDATE PROCESS test_valid_json_output.
    def test_valid_json_output(self, tmp_path):
        p = _write_trug(tmp_path, _minimal_trug())
        r = check_folder_trug(p, check_filesystem=False)
        output = format_json([r])
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert "folder" in parsed[0]
        assert "errors" in parsed[0]
        assert "warnings" in parsed[0]
        assert "stats" in parsed[0]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testcli AS A RECORD test_suite.
class TestCLI:
    """folder_check_command CLI interface."""

    # AGENT SHALL VALIDATE PROCESS test_check_single_file.
    def test_check_single_file(self, tmp_path):
        p = _write_trug(tmp_path, _minimal_trug())
        rc = folder_check_command([str(p)])
        assert rc == 0

    # AGENT SHALL VALIDATE PROCESS test_check_with_errors.
    def test_check_with_errors(self, tmp_path):
        trug = _minimal_trug()
        trug["nodes"][0]["type"] = "INVALID"
        p = _write_trug(tmp_path, trug)
        rc = folder_check_command([str(p)])
        assert rc == 1

    # AGENT SHALL VALIDATE PROCESS test_json_format.
    def test_json_format(self, tmp_path, capsys):
        p = _write_trug(tmp_path, _minimal_trug())
        rc = folder_check_command([str(p), "--format", "json"])
        assert rc == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert isinstance(parsed, list)

    # AGENT SHALL VALIDATE PROCESS test_quiet_mode.
    def test_quiet_mode(self, tmp_path, capsys):
        p = _write_trug(tmp_path, _minimal_trug())
        rc = folder_check_command([str(p), "--quiet"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "error(s)" in captured.out

    # AGENT SHALL VALIDATE PROCESS test_strict_mode_warnings.
    def test_strict_mode_warnings(self, tmp_path):
        # minimal trug has empty contains → warning
        p = _write_trug(tmp_path, _minimal_trug())
        rc = folder_check_command([str(p), "--strict"])
        assert rc == 1  # warnings treated as errors

    # AGENT SHALL VALIDATE PROCESS test_all_flag.
    def test_all_flag(self, tmp_path):
        sub = tmp_path / "X"
        sub.mkdir()
        _write_trug(sub, _minimal_trug())
        rc = folder_check_command(["--all", "--root", str(tmp_path)])
        assert rc == 0

    # AGENT SHALL VALIDATE PROCESS test_no_args_returns_error.
    def test_no_args_returns_error(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            folder_check_command([])
        assert exc_info.value.code == 2


# AGENT claude SHALL DEFINE RECORD testcheckresult AS A RECORD test_suite.
class TestCheckResult:
    """CheckResult dataclass."""

    # AGENT SHALL VALIDATE PROCESS test_ok_when_no_errors.
    def test_ok_when_no_errors(self):
        r = CheckResult("test.json")
        assert r.ok

    # AGENT SHALL VALIDATE PROCESS test_not_ok_with_errors.
    def test_not_ok_with_errors(self):
        r = CheckResult("test.json")
        r.errors.append("something bad")
        assert not r.ok

    # AGENT SHALL VALIDATE PROCESS test_to_dict.
    def test_to_dict(self):
        r = CheckResult("test.json")
        r.errors.append("err")
        r.warnings.append("warn")
        r.node_count = 5
        r.edge_count = 3
        d = r.to_dict()
        assert d["folder"] == "test.json"
        assert d["errors"] == ["err"]
        assert d["warnings"] == ["warn"]
        assert d["stats"]["nodes"] == 5
        assert d["stats"]["edges"] == 3
