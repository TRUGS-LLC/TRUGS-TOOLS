"""Tests for tcd and tfind navigation commands."""

import json
import pytest
from pathlib import Path

from trugs_tools.filesystem.tinit import tinit
from trugs_tools.filesystem.tadd import tadd
from trugs_tools.filesystem.tcd import tcd
from trugs_tools.filesystem.tfind import tfind
from trugs_tools.filesystem.tlink import tlink
from trugs_tools.filesystem.utils import load_graph


def _init_project(tmp_path):
    """Create a graph with multiple files for navigation tests."""
    (tmp_path / "main.py").write_text("import utils")
    (tmp_path / "utils.py").write_text("# utils")
    (tmp_path / "README.md").write_text("# Readme")
    (tmp_path / "config.yaml").write_text("key: value")
    tinit(tmp_path, name="TestProject", scan=True)
    return tmp_path


class TestTcd:
    def test_navigate_to_root(self, tmp_path):
        _init_project(tmp_path)
        result = tcd(tmp_path, "/")
        assert result["node"]["type"] == "FOLDER"
        assert len(result["children"]) == 4

    def test_navigate_to_root_empty_target(self, tmp_path):
        _init_project(tmp_path)
        result = tcd(tmp_path, "")
        assert result["node"]["type"] == "FOLDER"

    def test_navigate_by_id(self, tmp_path):
        _init_project(tmp_path)
        result = tcd(tmp_path, "main_py")
        assert result["node"]["id"] == "main_py"
        assert result["node"]["type"] == "SOURCE"

    def test_navigate_to_parent(self, tmp_path):
        _init_project(tmp_path)
        trug = load_graph(tmp_path)
        root_id = trug["nodes"][0]["id"]
        result = tcd(tmp_path, "..", current="main_py")
        assert result["node"]["id"] == root_id

    def test_navigate_parent_from_root(self, tmp_path):
        _init_project(tmp_path)
        trug = load_graph(tmp_path)
        root_id = trug["nodes"][0]["id"]
        with pytest.raises(ValueError, match="Already at root"):
            tcd(tmp_path, "..", current=root_id)

    def test_navigate_parent_no_current(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Current node required"):
            tcd(tmp_path, "..")

    def test_navigate_parent_invalid_current(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Current node not found"):
            tcd(tmp_path, "..", current="nonexistent")

    def test_navigate_invalid_node(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Node not found"):
            tcd(tmp_path, "nonexistent")

    def test_navigate_no_trug(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tcd(tmp_path, "/")

    def test_result_has_path(self, tmp_path):
        _init_project(tmp_path)
        result = tcd(tmp_path, "main_py")
        assert result["path"].startswith("/")
        assert "main.py" in result["path"]

    def test_result_has_children(self, tmp_path):
        _init_project(tmp_path)
        result = tcd(tmp_path, "/")
        assert isinstance(result["children"], list)
        for child in result["children"]:
            assert "id" in child
            assert "type" in child
            assert "name" in child

    def test_result_has_edges(self, tmp_path):
        _init_project(tmp_path)
        result = tcd(tmp_path, "/")
        assert isinstance(result["edges"], list)


class TestTfind:
    def test_find_by_type(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, node_type="SOURCE", format="json")
        assert isinstance(result, list)
        assert all(item["type"] == "SOURCE" for item in result)
        assert len(result) == 2  # main.py, utils.py

    def test_find_by_type_document(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, node_type="DOCUMENT", format="json")
        assert len(result) == 1
        assert result[0]["name"] == "README.md"

    def test_find_by_name_pattern(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, name_pattern=r"\.py$", format="json")
        names = [item["name"] for item in result]
        assert "main.py" in names
        assert "utils.py" in names
        assert "README.md" not in names

    def test_find_by_dimension(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, dimension="folder_structure", format="json")
        assert len(result) == 5  # root + 4 files

    def test_find_by_metric_level(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, metric_level="KILO_FOLDER", format="json")
        assert len(result) == 1
        assert result[0]["type"] == "FOLDER"

    def test_find_with_children(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, has_children=True, format="json")
        # Only root has children
        assert len(result) == 1
        assert result[0]["type"] == "FOLDER"

    def test_find_without_children(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, has_children=False, format="json")
        # All leaf nodes
        assert len(result) == 4

    def test_find_by_edge_relation(self, tmp_path):
        _init_project(tmp_path)
        # Add an edge
        tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")
        result = tfind(tmp_path, edge_relation="DEPENDS_ON", format="json")
        ids = [item["id"] for item in result]
        assert "main_py" in ids or "utils_py" in ids

    def test_find_custom_filter(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(
            tmp_path,
            custom_filter=lambda n: n.get("id", "").startswith("main"),
            format="json",
        )
        assert len(result) == 1
        assert result[0]["id"] == "main_py"

    def test_find_multiple_filters(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(
            tmp_path,
            node_type="SOURCE",
            name_pattern="main",
            format="json",
        )
        assert len(result) == 1
        assert result[0]["name"] == "main.py"

    def test_find_no_matches(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, node_type="NONEXISTENT", format="json")
        assert result == []

    def test_find_text_format(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, node_type="SOURCE", format="text")
        assert isinstance(result, str)
        assert "Found" in result
        assert "main.py" in result

    def test_find_no_trug(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tfind(tmp_path)

    def test_find_all(self, tmp_path):
        _init_project(tmp_path)
        result = tfind(tmp_path, format="json")
        assert len(result) == 5  # All nodes
