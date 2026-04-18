"""Tests for tinit, tadd, tls filesystem commands."""

import json
import pytest
from pathlib import Path

from trugs_tools.filesystem.tinit import tinit
from trugs_tools.filesystem.tadd import tadd
from trugs_tools.filesystem.tls import tls
from trugs_tools.filesystem.utils import TRUG_FILENAME, load_graph


class TestTinit:
    def test_basic_init(self, tmp_path):
        result = tinit(tmp_path)
        assert (tmp_path / TRUG_FILENAME).exists()
        assert result["name"].endswith("Folder")
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["type"] == "FOLDER"

    def test_init_with_name(self, tmp_path):
        result = tinit(tmp_path, name="MyProject")
        assert result["name"] == "MyProject Folder"
        assert result["nodes"][0]["properties"]["name"] == "MyProject"

    def test_init_with_description(self, tmp_path):
        result = tinit(tmp_path, description="My test project")
        assert result["description"] == "My test project"

    def test_init_already_exists(self, tmp_path):
        tinit(tmp_path)
        with pytest.raises(FileExistsError):
            tinit(tmp_path)

    def test_init_force_overwrite(self, tmp_path):
        result1 = tinit(tmp_path, name="First")
        result2 = tinit(tmp_path, name="Second", force=True)
        assert result2["name"] == "Second Folder"

    def test_init_with_scan(self, tmp_path):
        # Create some files
        (tmp_path / "main.py").write_text("# Python")
        (tmp_path / "README.md").write_text("# Readme")
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "subdir").mkdir()

        result = tinit(tmp_path, scan=True)
        # Root + 4 discovered items
        assert len(result["nodes"]) == 5
        root = result["nodes"][0]
        assert len(root["contains"]) == 4

    def test_init_scan_ignores_hidden(self, tmp_path):
        (tmp_path / ".hidden").write_text("hidden")
        (tmp_path / "visible.py").write_text("visible")

        result = tinit(tmp_path, scan=True)
        names = [n.get("properties", {}).get("name") for n in result["nodes"]]
        assert "visible.py" in names
        assert ".hidden" not in names

    def test_init_scan_ignores_pycache(self, tmp_path):
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "main.py").write_text("code")

        result = tinit(tmp_path, scan=True)
        names = [n.get("properties", {}).get("name") for n in result["nodes"]]
        assert "__pycache__" not in names

    def test_init_creates_valid_trug(self, tmp_path):
        from trugs_tools.validator import validate_trug
        result = tinit(tmp_path)
        validation = validate_trug(result)
        assert validation.valid

    def test_init_creates_valid_json(self, tmp_path):
        tinit(tmp_path)
        trug_path = tmp_path / TRUG_FILENAME
        loaded = json.loads(trug_path.read_text())
        assert loaded["version"] == "1.0.0"

    def test_tinit_with_qualifying_interest(self, tmp_path):
        result = tinit(tmp_path, qualifying_interest="Best Burgers")
        root_node = result["nodes"][0]
        assert root_node["properties"]["qualifying_interest"] == "Best Burgers"

    def test_tinit_without_qualifying_interest(self, tmp_path):
        result = tinit(tmp_path)
        root_node = result["nodes"][0]
        assert "qualifying_interest" not in root_node["properties"]


class TestTadd:
    def _init_dir(self, tmp_path):
        """Helper to initialize a directory with folder.trug.json."""
        tinit(tmp_path, name="Test")
        return tmp_path

    def test_add_single_file(self, tmp_path):
        self._init_dir(tmp_path)
        (tmp_path / "new_file.py").write_text("# code")
        result = tadd(tmp_path, ["new_file.py"])
        node_ids = [n["id"] for n in result["nodes"]]
        assert "new_file_py" in node_ids

    def test_add_multiple_files(self, tmp_path):
        self._init_dir(tmp_path)
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.md").write_text("")
        result = tadd(tmp_path, ["a.py", "b.md"])
        assert len(result["nodes"]) == 3  # root + 2

    def test_add_infers_type(self, tmp_path):
        self._init_dir(tmp_path)
        (tmp_path / "main.py").write_text("")
        result = tadd(tmp_path, ["main.py"])
        added = [n for n in result["nodes"] if n["id"] == "main_py"][0]
        assert added["type"] == "SOURCE"

    def test_add_override_type(self, tmp_path):
        self._init_dir(tmp_path)
        (tmp_path / "data.txt").write_text("")
        result = tadd(tmp_path, ["data.txt"], node_type="CONFIGURATION")
        added = [n for n in result["nodes"] if n["id"] == "data_txt"][0]
        assert added["type"] == "CONFIGURATION"

    def test_add_custom_parent(self, tmp_path):
        self._init_dir(tmp_path)
        trug = load_graph(tmp_path)
        root_id = trug["nodes"][0]["id"]

        # Add a subdirectory first
        (tmp_path / "sub").mkdir()
        tadd(tmp_path, ["sub"], node_type="FOLDER")

        # Add file to subdirectory
        (tmp_path / "sub" / "file.py").write_text("")
        result = tadd(tmp_path, ["file.py"], parent_id="sub")
        added = [n for n in result["nodes"] if n["id"] == "file_py"][0]
        assert added["parent_id"] == "sub"

    def test_add_duplicate_raises(self, tmp_path):
        self._init_dir(tmp_path)
        (tmp_path / "main.py").write_text("")
        tadd(tmp_path, ["main.py"])
        with pytest.raises(ValueError, match="already exists"):
            tadd(tmp_path, ["main.py"])

    def test_add_no_trug_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tadd(tmp_path, ["file.py"])

    def test_add_invalid_parent_raises(self, tmp_path):
        self._init_dir(tmp_path)
        with pytest.raises(ValueError, match="Parent node not found"):
            tadd(tmp_path, ["file.py"], parent_id="nonexistent")

    def test_add_updates_parent_contains(self, tmp_path):
        self._init_dir(tmp_path)
        (tmp_path / "app.py").write_text("")
        result = tadd(tmp_path, ["app.py"])
        root = result["nodes"][0]
        assert "app_py" in root["contains"]

    def test_add_with_purpose(self, tmp_path):
        self._init_dir(tmp_path)
        (tmp_path / "app.py").write_text("")
        result = tadd(tmp_path, ["app.py"], purpose="Main application")
        added = [n for n in result["nodes"] if n["id"] == "app_py"][0]
        assert added["properties"]["purpose"] == "Main application"


class TestTls:
    def _init_with_files(self, tmp_path):
        """Helper to create a graph with some files."""
        (tmp_path / "main.py").write_text("")
        (tmp_path / "README.md").write_text("")
        tinit(tmp_path, name="Test", scan=True)
        return tmp_path

    def test_list_text(self, tmp_path):
        self._init_with_files(tmp_path)
        result = tls(tmp_path, format="text")
        assert isinstance(result, str)
        assert "main.py" in result
        assert "README.md" in result

    def test_list_json(self, tmp_path):
        self._init_with_files(tmp_path)
        result = tls(tmp_path, format="json")
        assert isinstance(result, list)
        names = [item["name"] for item in result]
        assert "main.py" in names
        assert "README.md" in names

    def test_list_shows_type(self, tmp_path):
        self._init_with_files(tmp_path)
        result = tls(tmp_path, format="json")
        types = {item["name"]: item["type"] for item in result}
        assert types["main.py"] == "SOURCE"
        assert types["README.md"] == "DOCUMENT"

    def test_list_with_edges(self, tmp_path):
        self._init_with_files(tmp_path)
        # Add an edge
        from trugs_tools.filesystem.tlink import tlink
        trug = load_graph(tmp_path)
        node_ids = [n["id"] for n in trug["nodes"]]
        source_id = [n["id"] for n in trug["nodes"] if n.get("type") == "SOURCE"][0]
        doc_id = [n["id"] for n in trug["nodes"] if n.get("type") == "DOCUMENT"][0]
        tlink(tmp_path, source_id, doc_id, "REFERENCES")

        result = tls(tmp_path, show_edges=True, format="json")
        # At least one item should have edges
        has_edges = any(item.get("edges") for item in result)
        assert has_edges

    def test_list_empty_dir(self, tmp_path):
        tinit(tmp_path, name="Empty")
        result = tls(tmp_path, format="text")
        assert "(empty)" in result

    def test_list_specific_node(self, tmp_path):
        self._init_with_files(tmp_path)
        trug = load_graph(tmp_path)
        root_id = trug["nodes"][0]["id"]
        result = tls(tmp_path, node_id=root_id, format="json")
        assert isinstance(result, list)

    def test_list_invalid_node(self, tmp_path):
        tinit(tmp_path)
        with pytest.raises(ValueError, match="Node not found"):
            tls(tmp_path, node_id="nonexistent")

    def test_list_no_trug(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tls(tmp_path)

    def test_list_shows_edge_count(self, tmp_path):
        self._init_with_files(tmp_path)
        result = tls(tmp_path, format="json")
        for item in result:
            assert "edge_count" in item

    def test_list_shows_dimension(self, tmp_path):
        self._init_with_files(tmp_path)
        result = tls(tmp_path, format="json")
        for item in result:
            assert "dimension" in item
