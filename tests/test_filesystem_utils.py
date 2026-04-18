"""Tests for filesystem utilities."""

import json
import pytest
from pathlib import Path

from trugs_tools.filesystem.utils import (
    TRUG_FILENAME,
    create_backup,
    get_children,
    get_edges_for_node,
    get_node_by_id,
    get_root_node,
    infer_node_type,
    load_graph,
    make_node_id,
    restore_backup,
    save_graph,
    validate_graph,
)


def _make_trug(nodes=None, edges=None):
    """Create a minimal valid TRUG dict."""
    return {
        "name": "Test Folder",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": "Test",
        "dimensions": {"folder_structure": {"description": "Test", "base_level": "BASE"}},
        "capabilities": {"extensions": [], "vocabularies": ["project_v1"], "profiles": []},
        "nodes": nodes or [
            {"id": "root", "type": "FOLDER", "properties": {"name": "test"},
             "parent_id": None, "contains": ["child1"], "metric_level": "KILO_FOLDER",
             "dimension": "folder_structure"},
            {"id": "child1", "type": "SOURCE", "properties": {"name": "main.py"},
             "parent_id": "root", "contains": [], "metric_level": "BASE_SOURCE",
             "dimension": "folder_structure"},
        ],
        "edges": edges or [],
    }


class TestLoadSaveGraph:
    def test_load_graph(self, tmp_path):
        trug = _make_trug()
        (tmp_path / TRUG_FILENAME).write_text(json.dumps(trug), encoding="utf-8")
        loaded = load_graph(tmp_path)
        assert loaded["name"] == "Test Folder"

    def test_load_graph_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_graph(tmp_path)

    def test_save_graph(self, tmp_path):
        trug = _make_trug()
        path = save_graph(tmp_path, trug, backup=False)
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["name"] == "Test Folder"

    def test_save_graph_creates_backup(self, tmp_path):
        trug = _make_trug()
        save_graph(tmp_path, trug, backup=False)
        trug["name"] = "Updated"
        save_graph(tmp_path, trug, backup=True)
        backup = tmp_path / (TRUG_FILENAME + ".backup")
        assert backup.exists()
        original = json.loads(backup.read_text())
        assert original["name"] == "Test Folder"

    def test_save_graph_creates_directories(self, tmp_path):
        nested = tmp_path / "a" / "b"
        trug = _make_trug()
        path = save_graph(nested, trug, backup=False)
        assert path.exists()


class TestGraphQueries:
    def test_get_node_by_id(self):
        trug = _make_trug()
        node = get_node_by_id(trug, "root")
        assert node["type"] == "FOLDER"

    def test_get_node_by_id_not_found(self):
        trug = _make_trug()
        assert get_node_by_id(trug, "nonexistent") is None

    def test_get_children(self):
        trug = _make_trug()
        children = get_children(trug, "root")
        assert len(children) == 1
        assert children[0]["id"] == "child1"

    def test_get_children_sorted(self):
        trug = _make_trug(nodes=[
            {"id": "root", "type": "FOLDER", "properties": {"name": "test"},
             "parent_id": None, "contains": ["b", "a"]},
            {"id": "b", "type": "SOURCE", "properties": {"name": "b.py"}, "parent_id": "root"},
            {"id": "a", "type": "DOCUMENT", "properties": {"name": "a.md"}, "parent_id": "root"},
        ])
        children = get_children(trug, "root")
        # Sorted by type then name: DOCUMENT(a.md) before SOURCE(b.py)
        assert children[0]["id"] == "a"

    def test_get_edges_for_node(self):
        trug = _make_trug(edges=[
            {"from_id": "root", "to_id": "child1", "relation": "CONTAINS"},
            {"from_id": "child1", "to_id": "root", "relation": "DEPENDS_ON"},
        ])
        edges = get_edges_for_node(trug, "root")
        assert len(edges) == 2

    def test_get_edges_for_node_none(self):
        trug = _make_trug()
        edges = get_edges_for_node(trug, "root")
        assert len(edges) == 0

    def test_get_root_node_folder(self):
        trug = _make_trug()
        root = get_root_node(trug)
        assert root["id"] == "root"
        assert root["type"] == "FOLDER"

    def test_get_root_node_null_parent(self):
        trug = _make_trug(nodes=[
            {"id": "top", "type": "MODULE", "parent_id": None},
        ])
        root = get_root_node(trug)
        assert root["id"] == "top"

    def test_get_root_node_empty(self):
        trug = {"nodes": []}
        assert get_root_node(trug) is None


class TestInferNodeType:
    def test_python_source(self):
        assert infer_node_type("main.py") == "SOURCE"

    def test_go_source(self):
        assert infer_node_type("main.go") == "SOURCE"

    def test_markdown_document(self):
        assert infer_node_type("README.md") == "DOCUMENT"

    def test_json_configuration(self):
        assert infer_node_type("config.json") == "CONFIGURATION"

    def test_yaml_configuration(self):
        assert infer_node_type("config.yaml") == "CONFIGURATION"

    def test_toml_configuration(self):
        assert infer_node_type("pyproject.toml") == "CONFIGURATION"

    def test_trug_json_specification(self):
        assert infer_node_type("folder.trug.json") == "SPECIFICATION"

    def test_test_file(self):
        assert infer_node_type("test_main.test.py") == "TEST"

    def test_unknown_defaults_to_source(self):
        assert infer_node_type("Makefile") == "SOURCE"


class TestMakeNodeId:
    def test_simple(self):
        assert make_node_id("main.py") == "main_py"

    def test_with_dashes(self):
        assert make_node_id("my-file.txt") == "my_file_txt"

    def test_with_spaces(self):
        assert make_node_id("my file.txt") == "my_file_txt"


class TestValidateGraph:
    def test_valid_graph(self):
        trug = _make_trug()
        result = validate_graph(trug)
        assert result.valid

    def test_invalid_graph(self):
        result = validate_graph({"name": "bad"})
        assert not result.valid


class TestBackup:
    def test_create_backup(self, tmp_path):
        trug = _make_trug()
        save_graph(tmp_path, trug, backup=False)
        backup = create_backup(tmp_path)
        assert backup is not None
        assert backup.exists()

    def test_create_backup_no_source(self, tmp_path):
        assert create_backup(tmp_path) is None

    def test_restore_backup(self, tmp_path):
        trug = _make_trug()
        save_graph(tmp_path, trug, backup=False)
        create_backup(tmp_path)
        # Modify original
        trug["name"] = "Modified"
        save_graph(tmp_path, trug, backup=False)
        # Restore
        assert restore_backup(tmp_path)
        loaded = load_graph(tmp_path)
        assert loaded["name"] == "Test Folder"

    def test_restore_backup_no_backup(self, tmp_path):
        assert not restore_backup(tmp_path)
