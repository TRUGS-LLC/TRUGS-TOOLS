"""Tests for trugs folder-init command."""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from trugs_tools.filesystem.folder_init import (
    _build_edges,
    _count_lines,
    _infer_purpose,
    _make_node_id,
    _read_aaa_metadata,
    _read_pyproject_metadata,
    _scan_components,
    _scan_documents,
    _scan_examples,
    _scan_schemas,
    _scan_templates,
    _scan_tests,
    find_folders_without_trug,
    init_folder_trug,
)
from trugs_tools.cli import folder_init_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dir(tmpdir, *subdirs):
    """Create nested directories, return the path."""
    p = Path(tmpdir)
    for s in subdirs:
        p = p / s
    p.mkdir(parents=True, exist_ok=True)
    return p


def _make_file(tmpdir, name, content=""):
    """Create a file in tmpdir with given content."""
    p = Path(tmpdir) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _make_node_id tests
# ---------------------------------------------------------------------------

class TestMakeNodeId:
    def test_doc_readme(self):
        assert _make_node_id("doc", "README.md") == "doc_readme"

    def test_spec_folder_check(self):
        assert _make_node_id("spec", "SPEC_folder_check.md") == "spec_folder_check"

    def test_spec_specification_suffix(self):
        assert _make_node_id("spec", "MY_SPECIFICATION.md") == "spec_my"

    def test_comp_trugs_tools(self):
        assert _make_node_id("comp", "trugs_tools") == "comp_trugs_tools"

    def test_hyphen_to_underscore(self):
        assert _make_node_id("doc", "my-doc.md") == "doc_my_doc"

    def test_special_chars_removed(self):
        assert _make_node_id("doc", "my doc (v2).md") == "doc_my_doc_v2"


# ---------------------------------------------------------------------------
# Folder node ID tests (Fix 1 — explicit ID, not via _make_node_id)
# ---------------------------------------------------------------------------

class TestFolderNodeId:
    def test_folder_id_ends_with_folder(self):
        """FOLDER node ID should end with _folder, no double _folder suffix."""
        import shutil
        d = Path(tempfile.mkdtemp(prefix="myproject-"))
        try:
            (d / "README.md").write_text("# Hi")
            trug = init_folder_trug(d, run_tests=False)
            folder_node = [n for n in trug["nodes"] if n["type"] == "FOLDER"][0]
            assert folder_node["id"].endswith("_folder")
            assert not folder_node["id"].endswith("_folder_folder")
        finally:
            shutil.rmtree(d)

    def test_folder_id_hyphenated_name(self):
        """Ensure hyphenated folder names produce valid IDs."""
        import shutil
        d = Path(tempfile.mkdtemp(prefix="my-project-"))
        try:
            (d / "README.md").write_text("# Hi")
            trug = init_folder_trug(d, run_tests=False)
            folder_node = [n for n in trug["nodes"] if n["type"] == "FOLDER"][0]
            assert "-" not in folder_node["id"]
            assert folder_node["id"].endswith("_folder")
        finally:
            shutil.rmtree(d)


# ---------------------------------------------------------------------------
# _count_lines tests
# ---------------------------------------------------------------------------

class TestCountLines:
    def test_counts_non_empty(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\n\nline3\n", encoding="utf-8")
        assert _count_lines(f) == 2

    def test_missing_file(self, tmp_path):
        assert _count_lines(tmp_path / "missing.py") == 0


# ---------------------------------------------------------------------------
# _infer_purpose tests
# ---------------------------------------------------------------------------

class TestInferPurpose:
    def test_readme(self):
        assert "quickstart" in _infer_purpose("README.md").lower()

    def test_spec(self):
        assert "specification" in _infer_purpose("SPEC_folder_check.md").lower()

    def test_unknown(self):
        result = _infer_purpose("CUSTOM.md")
        assert "Custom" in result


# ---------------------------------------------------------------------------
# _scan_documents tests
# ---------------------------------------------------------------------------

class TestScanDocuments:
    def test_finds_md(self, tmp_path):
        _make_file(tmp_path, "README.md", "# README")
        _make_file(tmp_path, "AAA.md", "# AAA")
        _make_file(tmp_path, "NOTES.md", "# Notes")
        nodes = _scan_documents(tmp_path)
        assert len(nodes) == 3
        types = {n["type"] for n in nodes}
        assert types == {"DOCUMENT"}

    def test_separates_specs(self, tmp_path):
        _make_file(tmp_path, "README.md", "# README")
        _make_file(tmp_path, "FOO_SPEC.md", "# Spec")
        _make_file(tmp_path, "BAR_SPECIFICATION.md", "# Spec")
        nodes = _scan_documents(tmp_path)
        docs = [n for n in nodes if n["type"] == "DOCUMENT"]
        specs = [n for n in nodes if n["type"] == "SPECIFICATION"]
        assert len(docs) == 1
        assert len(specs) == 2

    def test_empty_folder(self, tmp_path):
        nodes = _scan_documents(tmp_path)
        assert nodes == []

    def test_no_recursion(self, tmp_path):
        subdir = _make_dir(tmp_path, "subdir")
        _make_file(subdir, "HIDDEN.md", "# Hidden")
        nodes = _scan_documents(tmp_path)
        assert nodes == []

    def test_node_format(self, tmp_path):
        _make_file(tmp_path, "README.md", "# README")
        nodes = _scan_documents(tmp_path)
        node = nodes[0]
        assert node["id"] == "doc_readme"
        assert node["type"] == "DOCUMENT"
        assert node["properties"]["name"] == "README.md"
        assert node["properties"]["format"] == "markdown"
        assert node["metric_level"] == "BASE_DOCUMENT"
        assert node["dimension"] == "folder_structure"
        assert node["contains"] == []


# ---------------------------------------------------------------------------
# _scan_components tests
# ---------------------------------------------------------------------------

class TestScanComponents:
    def test_finds_python(self, tmp_path):
        src = _make_dir(tmp_path, "src")
        _make_file(src, "main.py", "print('hello')\n")
        nodes = _scan_components(tmp_path)
        assert len(nodes) == 1
        assert nodes[0]["type"] == "COMPONENT"
        assert nodes[0]["properties"]["file_count"] == 1
        assert nodes[0]["properties"]["loc"] == 1

    def test_skips_tests(self, tmp_path):
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_foo.py", "pass\n")
        nodes = _scan_components(tmp_path)
        assert len(nodes) == 0

    def test_skips_pycache(self, tmp_path):
        cache = _make_dir(tmp_path, "__pycache__")
        _make_file(cache, "foo.py", "pass\n")
        nodes = _scan_components(tmp_path)
        assert len(nodes) == 0

    def test_skips_hidden(self, tmp_path):
        hidden = _make_dir(tmp_path, ".hidden")
        _make_file(hidden, "foo.py", "pass\n")
        nodes = _scan_components(tmp_path)
        assert len(nodes) == 0

    def test_skips_zzz(self, tmp_path):
        zzz = _make_dir(tmp_path, "ZZZ_old")
        _make_file(zzz, "foo.py", "pass\n")
        nodes = _scan_components(tmp_path)
        assert len(nodes) == 0

    def test_ignores_dirs_without_py(self, tmp_path):
        d = _make_dir(tmp_path, "data")
        _make_file(d, "data.csv", "a,b,c\n")
        nodes = _scan_components(tmp_path)
        assert len(nodes) == 0

    def test_component_node_format(self, tmp_path):
        src = _make_dir(tmp_path, "mylib")
        _make_file(src, "core.py", "def foo():\n    pass\n")
        nodes = _scan_components(tmp_path)
        node = nodes[0]
        assert node["id"] == "comp_mylib"
        assert node["metric_level"] == "DEKA_COMPONENT"
        assert node["properties"]["name"] == "mylib"

    def test_component_excludes_nested_tests(self, tmp_path):
        """Component file_count should exclude files in nested tests/ dirs."""
        src = _make_dir(tmp_path, "mylib")
        _make_file(src, "core.py", "def foo(): pass\n")
        nested_tests = _make_dir(src, "tests")
        _make_file(nested_tests, "test_core.py", "def test_foo(): pass\n")
        nodes = _scan_components(tmp_path)
        assert len(nodes) == 1
        assert nodes[0]["properties"]["file_count"] == 1  # only core.py, not test_core.py


# ---------------------------------------------------------------------------
# _scan_tests tests
# ---------------------------------------------------------------------------

class TestScanTests:
    def test_present(self, tmp_path):
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_foo.py", "def test_a(): pass\ndef test_b(): pass\n")
        _make_file(tests, "test_bar.py", "def test_c(): pass\n")
        node = _scan_tests(tmp_path, run_tests=False)
        assert node is not None
        assert node["type"] == "TEST_SUITE"
        assert node["id"] == "test_suite"
        assert node["properties"]["test_files"] == 2
        assert node["metric_level"] == "BASE_TEST_SUITE"

    def test_absent(self, tmp_path):
        node = _scan_tests(tmp_path)
        assert node is None

    def test_counts_both_patterns(self, tmp_path):
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_foo.py", "pass\n")
        _make_file(tests, "bar_test.py", "pass\n")
        node = _scan_tests(tmp_path, run_tests=False)
        assert node["properties"]["test_files"] == 2

    def test_scan_tests_prefers_local_venv(self, tmp_path):
        """When .venv/bin/python exists, it should be used."""
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_foo.py", "pass\n")
        venv_bin = _make_dir(tmp_path, ".venv", "bin")
        fake_python = _make_file(venv_bin, "python", "#!/bin/sh\n")  # fake venv python
        os.chmod(fake_python, 0o755)
        # Should not crash — falls back to file count when fake python fails
        node = _scan_tests(tmp_path, run_tests=True)
        assert node is not None
        assert node["properties"]["test_files"] == 1


# ---------------------------------------------------------------------------
# _scan_schemas tests
# ---------------------------------------------------------------------------

class TestScanSchemas:
    def test_schemas_dir(self, tmp_path):
        schemas = _make_dir(tmp_path, "schemas")
        _make_file(schemas, "core.json", "{}")
        _make_file(schemas, "ext.json", "{}")
        node = _scan_schemas(tmp_path)
        assert node is not None
        assert node["type"] == "SCHEMA"
        assert node["properties"]["schema_count"] == 2

    def test_schema_json_files(self, tmp_path):
        _make_file(tmp_path, "my.schema.json", "{}")
        node = _scan_schemas(tmp_path)
        assert node is not None
        assert node["properties"]["schema_count"] == 1

    def test_absent(self, tmp_path):
        node = _scan_schemas(tmp_path)
        assert node is None


# ---------------------------------------------------------------------------
# _scan_templates tests
# ---------------------------------------------------------------------------

class TestScanTemplates:
    def test_present(self, tmp_path):
        templates = _make_dir(tmp_path, "templates")
        _make_file(templates, "base.json", "{}")
        _make_file(templates, "ext.json", "{}")
        node = _scan_templates(tmp_path)
        assert node is not None
        assert node["type"] == "TEMPLATE"
        assert node["properties"]["template_count"] == 2

    def test_absent(self, tmp_path):
        node = _scan_templates(tmp_path)
        assert node is None


# ---------------------------------------------------------------------------
# _scan_examples tests
# ---------------------------------------------------------------------------

class TestScanExamples:
    def test_examples_upper(self, tmp_path):
        examples = _make_dir(tmp_path, "EXAMPLES")
        _make_file(examples, "ex1.json", "{}")
        _make_file(examples, "ex2.json", "{}")
        node = _scan_examples(tmp_path)
        assert node is not None
        assert node["type"] == "EXAMPLE_SET"
        assert node["properties"]["example_count"] == 2
        assert node["properties"]["name"] == "EXAMPLES/"

    def test_examples_lower(self, tmp_path):
        examples = _make_dir(tmp_path, "examples")
        _make_file(examples, "ex1.json", "{}")
        node = _scan_examples(tmp_path)
        assert node is not None
        assert node["properties"]["name"] == "examples/"

    def test_prefers_upper(self, tmp_path):
        _make_dir(tmp_path, "EXAMPLES")
        _make_dir(tmp_path, "examples")
        _make_file(tmp_path / "EXAMPLES", "ex.json", "{}")
        _make_file(tmp_path / "examples", "ex.json", "{}")
        node = _scan_examples(tmp_path)
        assert node["properties"]["name"] == "EXAMPLES/"

    def test_absent(self, tmp_path):
        node = _scan_examples(tmp_path)
        assert node is None


# ---------------------------------------------------------------------------
# _read_aaa_metadata tests
# ---------------------------------------------------------------------------

class TestReadAaaMetadata:
    def test_phase_status(self, tmp_path):
        _make_file(tmp_path, "AAA.md", (
            "# Project\n"
            "**Phase:** CODING\n"
            "**Status:** Active development\n"
            "**Version:** 1.0.0\n"
        ))
        meta = _read_aaa_metadata(tmp_path)
        assert meta["phase"] == "CODING"
        assert meta["status"] == "Active development"
        assert meta["version"] == "1.0.0"

    def test_missing(self, tmp_path):
        meta = _read_aaa_metadata(tmp_path)
        assert meta == {}

    def test_partial(self, tmp_path):
        _make_file(tmp_path, "AAA.md", "**Phase:** TESTING\n")
        meta = _read_aaa_metadata(tmp_path)
        assert meta["phase"] == "TESTING"
        assert "status" not in meta


# ---------------------------------------------------------------------------
# _read_pyproject_metadata tests
# ---------------------------------------------------------------------------

class TestReadPyprojectMetadata:
    def test_reads_metadata(self, tmp_path):
        _make_file(tmp_path, "pyproject.toml", (
            '[project]\n'
            'name = "my-tool"\n'
            'version = "2.0.0"\n'
            'description = "A great tool"\n'
        ))
        meta = _read_pyproject_metadata(tmp_path)
        assert meta["name"] == "my-tool"
        assert meta["version"] == "2.0.0"
        assert meta["description"] == "A great tool"

    def test_missing(self, tmp_path):
        meta = _read_pyproject_metadata(tmp_path)
        assert meta == {}

    def test_stops_at_next_section(self, tmp_path):
        _make_file(tmp_path, "pyproject.toml", (
            '[project]\n'
            'name = "my-tool"\n'
            '[build-system]\n'
            'requires = ["setuptools"]\n'
        ))
        meta = _read_pyproject_metadata(tmp_path)
        assert meta["name"] == "my-tool"
        assert "requires" not in meta


# ---------------------------------------------------------------------------
# _build_edges tests
# ---------------------------------------------------------------------------

class TestBuildEdges:
    def test_contains_edges(self):
        nodes = [
            {"id": "folder", "type": "FOLDER"},
            {"id": "doc_readme", "type": "DOCUMENT"},
            {"id": "comp_src", "type": "COMPONENT"},
        ]
        edges = _build_edges("folder", nodes)
        contains = [e for e in edges if e["relation"] == "contains"]
        assert len(contains) == 2
        targets = {e["to_id"] for e in contains}
        assert targets == {"doc_readme", "comp_src"}

    def test_tests_edges(self):
        nodes = [
            {"id": "folder", "type": "FOLDER"},
            {"id": "comp_src", "type": "COMPONENT"},
            {"id": "test_suite", "type": "TEST_SUITE"},
        ]
        edges = _build_edges("folder", nodes)
        tests_edges = [e for e in edges if e["relation"] == "tests"]
        assert len(tests_edges) == 1
        assert tests_edges[0]["from_id"] == "test_suite"
        assert tests_edges[0]["to_id"] == "comp_src"

    def test_no_tests_without_components(self):
        nodes = [
            {"id": "folder", "type": "FOLDER"},
            {"id": "test_suite", "type": "TEST_SUITE"},
        ]
        edges = _build_edges("folder", nodes)
        tests_edges = [e for e in edges if e["relation"] == "tests"]
        assert len(tests_edges) == 0


# ---------------------------------------------------------------------------
# init_folder_trug integration tests
# ---------------------------------------------------------------------------

class TestInitFolderTrug:
    def test_minimal_folder(self, tmp_path):
        """Folder with just README.md → FOLDER + 1 DOCUMENT node."""
        _make_file(tmp_path, "README.md", "# Hello\n")
        trug = init_folder_trug(tmp_path, run_tests=False)
        assert trug["type"] == "PROJECT"
        assert len(trug["nodes"]) == 2  # FOLDER + DOCUMENT
        types = {n["type"] for n in trug["nodes"]}
        assert "FOLDER" in types
        assert "DOCUMENT" in types

    def test_full_folder(self, tmp_path):
        """Folder with all node types generates all 8 types."""
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "DESIGN_SPEC.md", "# Spec")
        src = _make_dir(tmp_path, "src")
        _make_file(src, "main.py", "print('hi')\n")
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_main.py", "def test_a(): pass\n")
        schemas = _make_dir(tmp_path, "schemas")
        _make_file(schemas, "core.json", "{}")
        templates = _make_dir(tmp_path, "templates")
        _make_file(templates, "base.json", "{}")
        examples = _make_dir(tmp_path, "EXAMPLES")
        _make_file(examples, "ex1.json", "{}")

        trug = init_folder_trug(tmp_path, run_tests=False)
        types = {n["type"] for n in trug["nodes"]}
        assert types == {
            "FOLDER", "DOCUMENT", "SPECIFICATION", "COMPONENT",
            "TEST_SUITE", "SCHEMA", "TEMPLATE", "EXAMPLE_SET",
        }

    def test_existing_trug_fails(self, tmp_path):
        _make_file(tmp_path, "folder.trug.json", "{}")
        with pytest.raises(FileExistsError):
            init_folder_trug(tmp_path)

    def test_force_overwrites(self, tmp_path):
        _make_file(tmp_path, "folder.trug.json", "{}")
        _make_file(tmp_path, "README.md", "# Hi")
        trug = init_folder_trug(tmp_path, force=True, run_tests=False)
        assert trug["type"] == "PROJECT"

    def test_not_a_directory(self, tmp_path):
        f = _make_file(tmp_path, "notadir.txt", "hi")
        with pytest.raises(NotADirectoryError):
            init_folder_trug(f)

    def test_folder_node_is_root(self, tmp_path):
        _make_file(tmp_path, "README.md", "# Hi")
        trug = init_folder_trug(tmp_path, run_tests=False)
        folder_nodes = [n for n in trug["nodes"] if n["type"] == "FOLDER"]
        assert len(folder_nodes) == 1
        assert folder_nodes[0]["parent_id"] is None

    def test_contains_array(self, tmp_path):
        _make_file(tmp_path, "README.md", "# Hi")
        src = _make_dir(tmp_path, "src")
        _make_file(src, "main.py", "pass\n")
        trug = init_folder_trug(tmp_path, run_tests=False)
        folder_node = [n for n in trug["nodes"] if n["type"] == "FOLDER"][0]
        child_ids = folder_node["contains"]
        assert "doc_readme" in child_ids

    def test_children_parent_id(self, tmp_path):
        _make_file(tmp_path, "README.md", "# Hi")
        trug = init_folder_trug(tmp_path, run_tests=False)
        folder_node = [n for n in trug["nodes"] if n["type"] == "FOLDER"][0]
        for node in trug["nodes"]:
            if node["type"] != "FOLDER":
                assert node["parent_id"] == folder_node["id"]

    def test_edges_generated(self, tmp_path):
        _make_file(tmp_path, "README.md", "# Hi")
        src = _make_dir(tmp_path, "src")
        _make_file(src, "main.py", "pass\n")
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_main.py", "pass\n")
        trug = init_folder_trug(tmp_path, run_tests=False)
        contains_edges = [e for e in trug["edges"] if e["relation"] == "contains"]
        tests_edges = [e for e in trug["edges"] if e["relation"] == "tests"]
        assert len(contains_edges) >= 3  # doc + comp + test_suite
        assert len(tests_edges) == 1

    def test_trug_structure(self, tmp_path):
        """Generated TRUG has required top-level keys."""
        _make_file(tmp_path, "README.md", "# Hi")
        trug = init_folder_trug(tmp_path, run_tests=False)
        required_keys = {"name", "version", "type", "dimensions", "capabilities", "nodes", "edges"}
        assert required_keys.issubset(set(trug.keys()))
        assert "folder_structure" in trug["dimensions"]

    def test_with_aaa_metadata(self, tmp_path):
        _make_file(tmp_path, "AAA.md", "**Phase:** CODING\n**Status:** Active\n")
        _make_file(tmp_path, "README.md", "# Hi")
        trug = init_folder_trug(tmp_path, run_tests=False)
        folder_node = [n for n in trug["nodes"] if n["type"] == "FOLDER"][0]
        assert folder_node["properties"]["phase"] == "CODING"

    def test_with_pyproject_metadata(self, tmp_path):
        _make_file(tmp_path, "pyproject.toml", (
            '[project]\nname = "my-tool"\nversion = "3.0.0"\n'
            'description = "Amazing tool"\n'
        ))
        _make_file(tmp_path, "README.md", "# Hi")
        trug = init_folder_trug(tmp_path, run_tests=False)
        assert trug["version"] == "3.0.0"
        assert trug["description"] == "Amazing tool"


# ---------------------------------------------------------------------------
# Integration test: run against TRUGS_TOOLS folder
# ---------------------------------------------------------------------------

class TestIntegrationTrugsTools:
    """Integration test against the real TRUGS_TOOLS folder."""

    @pytest.fixture
    def trugs_tools_path(self):
        # Find the TRUGS_TOOLS folder relative to this test
        here = Path(__file__).resolve().parent
        trugs_tools = here.parent  # TRUGS_TOOLS/
        if not (trugs_tools / "pyproject.toml").exists():
            pytest.skip("TRUGS_TOOLS folder not found")
        return trugs_tools

    def test_init_trugs_tools(self, trugs_tools_path):
        trug = init_folder_trug(trugs_tools_path, force=True, run_tests=False)
        assert len(trug["nodes"]) >= 10
        types = {n["type"] for n in trug["nodes"]}
        assert "FOLDER" in types
        assert "COMPONENT" in types
        assert "TEST_SUITE" in types
        assert "DOCUMENT" in types

    def test_init_validates(self, trugs_tools_path):
        """Generated TRUG passes trugs-validate."""
        from trugs_tools.validator import validate_trug
        trug = init_folder_trug(trugs_tools_path, force=True, run_tests=False)
        # Write to temp file and validate
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(trug, f, indent=2)
            tmp_path = f.name
        try:
            result = validate_trug(tmp_path)
            assert result.valid, f"Validation errors: {result.errors}"
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# find_folders_without_trug tests
# ---------------------------------------------------------------------------

class TestFindFoldersWithoutTrug:
    def test_finds_missing(self, tmp_path):
        folder1 = _make_dir(tmp_path, "folder1")
        _make_file(folder1, "README.md", "# Hi")
        folder2 = _make_dir(tmp_path, "folder2")
        _make_file(folder2, "folder.trug.json", "{}")
        _make_file(folder2, "README.md", "# Hi")
        result = find_folders_without_trug(tmp_path)
        paths = [str(p) for p in result]
        assert str(folder1) in paths
        assert str(folder2) not in paths

    def test_skips_hidden(self, tmp_path):
        hidden = _make_dir(tmp_path, ".hidden")
        _make_file(hidden, "README.md", "# Hi")
        result = find_folders_without_trug(tmp_path)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestFolderInitCli:
    def test_single_folder(self, tmp_path):
        _make_file(tmp_path, "README.md", "# Hello")
        ret = folder_init_command([str(tmp_path), "--no-tests"])
        assert ret == 0
        assert (tmp_path / "folder.trug.json").exists()
        trug = json.loads((tmp_path / "folder.trug.json").read_text())
        assert trug["type"] == "PROJECT"

    def test_dry_run(self, tmp_path, capsys):
        _make_file(tmp_path, "README.md", "# Hello")
        ret = folder_init_command([str(tmp_path), "--dry-run", "--no-tests"])
        assert ret == 0
        assert not (tmp_path / "folder.trug.json").exists()
        captured = capsys.readouterr()
        trug = json.loads(captured.out)
        assert trug["type"] == "PROJECT"

    def test_force(self, tmp_path):
        _make_file(tmp_path, "README.md", "# Hello")
        _make_file(tmp_path, "folder.trug.json", "{}")
        ret = folder_init_command([str(tmp_path), "--force", "--no-tests"])
        assert ret == 0

    def test_existing_without_force(self, tmp_path):
        _make_file(tmp_path, "folder.trug.json", "{}")
        ret = folder_init_command([str(tmp_path)])
        assert ret == 1

    def test_missing_path(self, tmp_path):
        missing = str(tmp_path / "nonexistent")
        ret = folder_init_command([missing])
        assert ret == 1

    def test_no_tests_flag(self, tmp_path):
        _make_file(tmp_path, "README.md", "# Hello")
        tests_dir = _make_dir(tmp_path, "tests")
        _make_file(tests_dir, "test_foo.py", "pass\n")
        ret = folder_init_command([str(tmp_path), "--no-tests"])
        assert ret == 0
        trug = json.loads((tmp_path / "folder.trug.json").read_text())
        test_nodes = [n for n in trug["nodes"] if n["type"] == "TEST_SUITE"]
        assert len(test_nodes) == 1

    def test_all_flag(self, tmp_path):
        """--all generates TRUGs for folders missing them."""
        folder1 = _make_dir(tmp_path, "project_a")
        _make_file(folder1, "README.md", "# A")
        folder2 = _make_dir(tmp_path, "project_b")
        _make_file(folder2, "README.md", "# B")
        # folder3 already has a TRUG — should be skipped
        folder3 = _make_dir(tmp_path, "project_c")
        _make_file(folder3, "README.md", "# C")
        _make_file(folder3, "folder.trug.json", "{}")

        ret = folder_init_command(["--all", "--root", str(tmp_path), "--no-tests"])
        assert ret == 0
        assert (folder1 / "folder.trug.json").exists()
        assert (folder2 / "folder.trug.json").exists()
        # folder3's TRUG should be unchanged (not overwritten)
        assert json.loads((folder3 / "folder.trug.json").read_text()) == {}

    def test_all_dry_run(self, tmp_path, capsys):
        """--all --dry-run prints but doesn't write."""
        folder1 = _make_dir(tmp_path, "project_a")
        _make_file(folder1, "README.md", "# A")
        ret = folder_init_command(["--all", "--root", str(tmp_path), "--dry-run", "--no-tests"])
        assert ret == 0
        assert not (folder1 / "folder.trug.json").exists()
        captured = capsys.readouterr()
        assert "project_a" in captured.out

    def test_all_no_qualifying_folders(self, tmp_path, capsys):
        """--all with no qualifying folders returns 0."""
        ret = folder_init_command(["--all", "--root", str(tmp_path), "--no-tests"])
        assert ret == 0


# ---------------------------------------------------------------------------
# VG-1: test_count_source tracking (Fix 1 — #453)
# ---------------------------------------------------------------------------

class TestTestCountSource:
    """VG-1: _scan_tests records test_count_source to distinguish pytest vs fallback."""

    def test_pytest_failure_fallback_file_count(self, tmp_path, caplog):
        """VG-1: pytest failure → warning + fallback_file_count."""
        import logging
        import subprocess
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_foo.py", "def test_a(): pass\n")
        _make_file(tests, "test_bar.py", "def test_b(): pass\n")

        # Mock subprocess.run to simulate pytest failure
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=2, stdout="", stderr="error"
        )
        with mock.patch("trugs_tools.filesystem.folder_init.subprocess.run", return_value=fake_result):
            with caplog.at_level(logging.WARNING, logger="trugs_tools.filesystem.folder_init"):
                node = _scan_tests(tmp_path, run_tests=True)

        assert node is not None
        assert node["properties"]["test_count_source"] == "fallback_file_count"
        assert node["properties"]["test_count"] == 2  # file count
        # Should have emitted a warning
        assert any("falling back" in r.message for r in caplog.records)

    def test_pytest_missing_fallback_file_count(self, tmp_path, caplog):
        """VG-1: pytest not found → warning + fallback_file_count."""
        import logging
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_foo.py", "def test_a(): pass\n")

        with mock.patch(
            "trugs_tools.filesystem.folder_init.subprocess.run",
            side_effect=FileNotFoundError("python not found"),
        ):
            with caplog.at_level(logging.WARNING, logger="trugs_tools.filesystem.folder_init"):
                node = _scan_tests(tmp_path, run_tests=True)

        assert node is not None
        assert node["properties"]["test_count_source"] == "fallback_file_count"
        assert any("falling back" in r.message for r in caplog.records)

    def test_pytest_success_source(self, tmp_path):
        """VG-1b: pytest success → pytest source."""
        import subprocess
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_foo.py", "def test_a(): pass\ndef test_b(): pass\n")

        # Mock subprocess.run to simulate pytest success
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="2 tests collected\n", stderr=""
        )
        with mock.patch("trugs_tools.filesystem.folder_init.subprocess.run", return_value=fake_result):
            node = _scan_tests(tmp_path, run_tests=True)

        assert node is not None
        assert node["properties"]["test_count_source"] == "pytest"
        assert node["properties"]["test_count"] == 2

    def test_run_tests_false_always_fallback(self, tmp_path):
        """When run_tests=False, source is always fallback_file_count."""
        tests = _make_dir(tmp_path, "tests")
        _make_file(tests, "test_a.py", "pass\n")
        node = _scan_tests(tmp_path, run_tests=False)
        assert node["properties"]["test_count_source"] == "fallback_file_count"
