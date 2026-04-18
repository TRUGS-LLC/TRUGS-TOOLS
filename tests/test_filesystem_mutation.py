"""Tests for tmove, tlink, tdim mutation commands."""

import json
import pytest
from pathlib import Path

from trugs_tools.filesystem.tinit import tinit
from trugs_tools.filesystem.tadd import tadd
from trugs_tools.filesystem.tmove import tmove
from trugs_tools.filesystem.tlink import tlink, tunlink, VALID_RELATIONS
from trugs_tools.filesystem.tdim import tdim, tdim_add, tdim_remove, tdim_list, tdim_set
from trugs_tools.filesystem.utils import load_graph, get_node_by_id


def _init_project(tmp_path):
    """Create a project with some files."""
    (tmp_path / "main.py").write_text("# main")
    (tmp_path / "utils.py").write_text("# utils")
    (tmp_path / "README.md").write_text("# readme")
    tinit(tmp_path, name="Test", scan=True)
    return tmp_path


# AGENT claude SHALL DEFINE RECORD testtmove AS A RECORD test_suite.
class TestTmove:
    # AGENT SHALL VALIDATE PROCESS test_rename_node.
    def test_rename_node(self, tmp_path):
        _init_project(tmp_path)
        result = tmove(tmp_path, "main_py", new_name="app.py")
        node = get_node_by_id(result, "main_py")
        assert node["properties"]["name"] == "app.py"
        # File should be renamed
        assert (tmp_path / "app.py").exists()
        assert not (tmp_path / "main.py").exists()

    # AGENT SHALL VALIDATE PROCESS test_reparent_node.
    def test_reparent_node(self, tmp_path):
        _init_project(tmp_path)
        # Add a subdirectory node
        (tmp_path / "lib").mkdir()
        tadd(tmp_path, ["lib"], node_type="FOLDER")

        result = tmove(tmp_path, "utils_py", new_parent_id="lib")
        node = get_node_by_id(result, "utils_py")
        assert node["parent_id"] == "lib"

        # Check old parent no longer contains node
        root = [n for n in result["nodes"] if n["type"] == "FOLDER" and n.get("parent_id") is None][0]
        assert "utils_py" not in root.get("contains", [])

        # Check new parent contains node
        lib_node = get_node_by_id(result, "lib")
        assert "utils_py" in lib_node.get("contains", [])

    # AGENT SHALL VALIDATE PROCESS test_move_requires_action.
    def test_move_requires_action(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Must specify"):
            tmove(tmp_path, "main_py")

    # AGENT SHALL VALIDATE PROCESS test_move_node_not_found.
    def test_move_node_not_found(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Node not found"):
            tmove(tmp_path, "nonexistent", new_name="test.py")

    # AGENT SHALL VALIDATE PROCESS test_move_new_parent_not_found.
    def test_move_new_parent_not_found(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="New parent node not found"):
            tmove(tmp_path, "main_py", new_parent_id="nonexistent")

    # AGENT SHALL VALIDATE PROCESS test_rename_nonexistent_file_still_updates_graph.
    def test_rename_nonexistent_file_still_updates_graph(self, tmp_path):
        _init_project(tmp_path)
        # Remove the physical file but keep the graph node
        (tmp_path / "main.py").unlink()
        result = tmove(tmp_path, "main_py", new_name="app.py")
        node = get_node_by_id(result, "main_py")
        assert node["properties"]["name"] == "app.py"

    # AGENT SHALL VALIDATE PROCESS test_move_no_trug.
    def test_move_no_trug(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tmove(tmp_path, "node", new_name="test")


# AGENT claude SHALL DEFINE RECORD testtlink AS A RECORD test_suite.
class TestTlink:
    # AGENT SHALL VALIDATE PROCESS test_create_edge.
    def test_create_edge(self, tmp_path):
        _init_project(tmp_path)
        result = tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")
        edges = result["edges"]
        assert len(edges) == 1
        assert edges[0]["from_id"] == "main_py"
        assert edges[0]["to_id"] == "utils_py"
        assert edges[0]["relation"] == "DEPENDS_ON"

    # AGENT SHALL VALIDATE PROCESS test_create_edge_with_properties.
    def test_create_edge_with_properties(self, tmp_path):
        _init_project(tmp_path)
        props = {"weight": 1.0, "description": "test edge"}
        result = tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON",
                       properties=props)
        assert result["edges"][0]["properties"] == props

    # AGENT SHALL VALIDATE PROCESS test_invalid_relation.
    def test_invalid_relation(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Invalid relation"):
            tlink(tmp_path, "main_py", "utils_py", "INVALID_RELATION")

    # AGENT SHALL VALIDATE PROCESS test_source_not_found.
    def test_source_not_found(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Source node not found"):
            tlink(tmp_path, "nonexistent", "utils_py", "DEPENDS_ON")

    # AGENT SHALL VALIDATE PROCESS test_target_not_found.
    def test_target_not_found(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Target node not found"):
            tlink(tmp_path, "main_py", "nonexistent", "DEPENDS_ON")

    # AGENT SHALL VALIDATE PROCESS test_self_reference.
    def test_self_reference(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Cannot create edge from a node to itself"):
            tlink(tmp_path, "main_py", "main_py", "DEPENDS_ON")

    # AGENT SHALL VALIDATE PROCESS test_duplicate_edge.
    def test_duplicate_edge(self, tmp_path):
        _init_project(tmp_path)
        tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")
        with pytest.raises(ValueError, match="Edge already exists"):
            tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")

    # AGENT SHALL VALIDATE PROCESS test_multiple_edges_different_relations.
    def test_multiple_edges_different_relations(self, tmp_path):
        _init_project(tmp_path)
        tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")
        result = tlink(tmp_path, "main_py", "utils_py", "REFERENCES")
        assert len(result["edges"]) == 2

    # AGENT SHALL VALIDATE PROCESS test_valid_relations.
    def test_valid_relations(self):
        """All documented relations should be in VALID_RELATIONS."""
        assert "CONTAINS" in VALID_RELATIONS
        assert "DEPENDS_ON" in VALID_RELATIONS
        assert "IMPLEMENTS" in VALID_RELATIONS
        assert "TESTS" in VALID_RELATIONS
        assert "DOCUMENTS" in VALID_RELATIONS

    # AGENT SHALL VALIDATE PROCESS test_no_trug.
    def test_no_trug(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tlink(tmp_path, "a", "b", "DEPENDS_ON")

    # AGENT SHALL VALIDATE PROCESS test_create_edge_with_weight.
    def test_create_edge_with_weight(self, tmp_path):
        _init_project(tmp_path)
        result = tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON", weight=0.8)
        edge = result["edges"][0]
        assert "weight" in edge
        assert edge["weight"] == 0.8

    # AGENT SHALL VALIDATE PROCESS test_create_edge_with_weight_zero.
    def test_create_edge_with_weight_zero(self, tmp_path):
        _init_project(tmp_path)
        result = tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON", weight=0.0)
        assert result["edges"][0]["weight"] == 0.0

    # AGENT SHALL VALIDATE PROCESS test_create_edge_with_weight_one.
    def test_create_edge_with_weight_one(self, tmp_path):
        _init_project(tmp_path)
        result = tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON", weight=1.0)
        assert result["edges"][0]["weight"] == 1.0

    # AGENT SHALL VALIDATE PROCESS test_create_edge_with_weight_out_of_range.
    def test_create_edge_with_weight_out_of_range(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Weight must be a number between 0.0 and 1.0"):
            tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON", weight=1.5)

    # AGENT SHALL VALIDATE PROCESS test_create_edge_with_negative_weight.
    def test_create_edge_with_negative_weight(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Weight must be a number between 0.0 and 1.0"):
            tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON", weight=-0.1)

    # AGENT SHALL VALIDATE PROCESS test_create_edge_with_string_weight.
    def test_create_edge_with_string_weight(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises((ValueError, TypeError)):
            tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON", weight="high")

    # AGENT SHALL VALIDATE PROCESS test_create_edge_without_weight.
    def test_create_edge_without_weight(self, tmp_path):
        _init_project(tmp_path)
        result = tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON", weight=None)
        assert "weight" not in result["edges"][0]


# AGENT claude SHALL DEFINE RECORD testtunlink AS A RECORD test_suite.
class TestTunlink:
    # AGENT SHALL VALIDATE PROCESS test_remove_edge.
    def test_remove_edge(self, tmp_path):
        _init_project(tmp_path)
        tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")
        result = tunlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")
        assert len(result["edges"]) == 0

    # AGENT SHALL VALIDATE PROCESS test_remove_all_edges_between.
    def test_remove_all_edges_between(self, tmp_path):
        _init_project(tmp_path)
        tlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")
        tlink(tmp_path, "main_py", "utils_py", "REFERENCES")
        result = tunlink(tmp_path, "main_py", "utils_py")
        assert len(result["edges"]) == 0

    # AGENT SHALL VALIDATE PROCESS test_remove_nonexistent_edge.
    def test_remove_nonexistent_edge(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="No matching edge"):
            tunlink(tmp_path, "main_py", "utils_py", "DEPENDS_ON")


# AGENT claude SHALL DEFINE RECORD testtdim AS A RECORD test_suite.
class TestTdim:
    # AGENT SHALL VALIDATE PROCESS test_add_dimension.
    def test_add_dimension(self, tmp_path):
        _init_project(tmp_path)
        result = tdim_add(tmp_path, "security", "Security dimension", "SECURE")
        assert "security" in result["dimensions"]
        assert result["dimensions"]["security"]["description"] == "Security dimension"

    # AGENT SHALL VALIDATE PROCESS test_add_duplicate_dimension.
    def test_add_duplicate_dimension(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="already exists"):
            tdim_add(tmp_path, "folder_structure")

    # AGENT SHALL VALIDATE PROCESS test_remove_dimension.
    def test_remove_dimension(self, tmp_path):
        _init_project(tmp_path)
        tdim_add(tmp_path, "new_dim", "test")
        result = tdim_remove(tmp_path, "new_dim")
        assert "new_dim" not in result["dimensions"]

    # AGENT SHALL VALIDATE PROCESS test_remove_dimension_in_use.
    def test_remove_dimension_in_use(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="is used by"):
            tdim_remove(tmp_path, "folder_structure")

    # AGENT SHALL VALIDATE PROCESS test_remove_dimension_force.
    def test_remove_dimension_force(self, tmp_path):
        _init_project(tmp_path)
        result = tdim_remove(tmp_path, "folder_structure", force=True)
        assert "folder_structure" not in result["dimensions"]
        # Nodes should have empty dimension
        for node in result["nodes"]:
            assert node.get("dimension", "") == ""

    # AGENT SHALL VALIDATE PROCESS test_remove_nonexistent_dimension.
    def test_remove_nonexistent_dimension(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            tdim_remove(tmp_path, "nonexistent")

    # AGENT SHALL VALIDATE PROCESS test_list_dimensions_text.
    def test_list_dimensions_text(self, tmp_path):
        _init_project(tmp_path)
        result = tdim_list(tmp_path, format="text")
        assert isinstance(result, str)
        assert "folder_structure" in result

    # AGENT SHALL VALIDATE PROCESS test_list_dimensions_json.
    def test_list_dimensions_json(self, tmp_path):
        _init_project(tmp_path)
        result = tdim_list(tmp_path, format="json")
        assert isinstance(result, dict)
        assert "folder_structure" in result
        assert result["folder_structure"]["node_count"] > 0

    # AGENT SHALL VALIDATE PROCESS test_set_dimension.
    def test_set_dimension(self, tmp_path):
        _init_project(tmp_path)
        tdim_add(tmp_path, "new_dim")
        result = tdim_set(tmp_path, "main_py", "new_dim")
        node = get_node_by_id(result, "main_py")
        assert node["dimension"] == "new_dim"

    # AGENT SHALL VALIDATE PROCESS test_set_dimension_node_not_found.
    def test_set_dimension_node_not_found(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Node not found"):
            tdim_set(tmp_path, "nonexistent", "folder_structure")

    # AGENT SHALL VALIDATE PROCESS test_set_dimension_not_found.
    def test_set_dimension_not_found(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Dimension not found"):
            tdim_set(tmp_path, "main_py", "nonexistent")

    # AGENT SHALL VALIDATE PROCESS test_dispatcher.
    def test_dispatcher(self, tmp_path):
        _init_project(tmp_path)
        result = tdim(tmp_path, "list", format="json")
        assert isinstance(result, dict)

    # AGENT SHALL VALIDATE PROCESS test_dispatcher_invalid_action.
    def test_dispatcher_invalid_action(self, tmp_path):
        _init_project(tmp_path)
        with pytest.raises(ValueError, match="Unknown action"):
            tdim(tmp_path, "invalid")
