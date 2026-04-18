"""Tests for trugs folder-map command."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from trugs_tools.filesystem.folder_map import (
    MapResult,
    FolderInfo,
    map_folder_trugs,
    _folder_alias,
    _find_folder_node,
    _load_folder_trugs,
    _is_cross_folder_ref,
    _parse_cross_folder_ref,
    _resolve_cross_folder_edges,
    _make_folder_node_id,
    _make_folder_node,
    _find_orphaned_folders,
    _build_root_graph,
)
from trugs_tools.cli import folder_map_command


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


def _minimal_folder_trug(folder_name, extra_nodes=None, extra_edges=None):
    """Create a minimal valid folder.trug.json dict."""
    folder_id = f"{folder_name.lower()}_folder"
    nodes = [
        {
            "id": folder_id,
            "type": "FOLDER",
            "properties": {
                "name": folder_name,
                "purpose": f"{folder_name} project folder",
                "phase": "CODING",
                "status": "Active",
                "version": "1.0.0",
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
    ]
    edges = [
        {
            "from_id": folder_id,
            "to_id": "doc_readme",
            "relation": "contains",
            "weight": 1.0,
        },
    ]
    if extra_nodes:
        nodes.extend(extra_nodes)
    if extra_edges:
        edges.extend(extra_edges)
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
        "nodes": nodes,
        "edges": edges,
    }


def _setup_repo(tmp_dir, folder_configs):
    """Set up a fake repo structure with multiple folder TRUGs.

    folder_configs is a list of dicts with keys:
        name: folder name (e.g., "FOLDER_A")
        extra_nodes: optional extra nodes
        extra_edges: optional extra edges
    """
    root = Path(tmp_dir)
    for config in folder_configs:
        name = config["name"]
        folder_dir = root / name
        folder_dir.mkdir(parents=True, exist_ok=True)
        trug = _minimal_folder_trug(
            name,
            extra_nodes=config.get("extra_nodes"),
            extra_edges=config.get("extra_edges"),
        )
        _make_file(folder_dir, "folder.trug.json", json.dumps(trug, indent=2))
        _make_file(folder_dir, "README.md", f"# {name}\n")
    return root


# ===========================================================================
# Unit Tests: Helpers
# ===========================================================================

class TestFolderAlias:
    def test_uppercase(self):
        assert _folder_alias("TRUGS_TOOLS") == "trugs_tools"

    def test_mixed_case(self):
        assert _folder_alias("Code_Factory") == "code_factory"

    def test_already_lower(self):
        assert _folder_alias("packages") == "packages"


class TestCrossFolderRef:
    def test_is_cross_folder(self):
        assert _is_cross_folder_ref("trugs_tools:comp_validator") is True

    def test_is_not_cross_folder(self):
        assert _is_cross_folder_ref("comp_validator") is False

    def test_parse(self):
        alias, node = _parse_cross_folder_ref("trugs_protocol:spec_validation")
        assert alias == "trugs_protocol"
        assert node == "spec_validation"

    def test_parse_uppercase(self):
        alias, node = _parse_cross_folder_ref("TRUGS_TOOLS:comp_validator")
        assert alias == "trugs_tools"
        assert node == "comp_validator"


class TestFindFolderNode:
    def test_found(self):
        trug = _minimal_folder_trug("TEST")
        node = _find_folder_node(trug)
        assert node is not None
        assert node["type"] == "FOLDER"

    def test_not_found(self):
        trug = {"nodes": [{"id": "x", "type": "DOCUMENT"}]}
        assert _find_folder_node(trug) is None

    def test_empty(self):
        assert _find_folder_node({}) is None


class TestMakeFolderNodeId:
    def test_basic(self):
        assert _make_folder_node_id("trugs_tools") == "folder_trugs_tools"


# ===========================================================================
# Unit Tests: Load folder TRUGs
# ===========================================================================

class TestLoadFolderTrugs:
    def test_loads_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
                {"name": "FOLDER_B"},
            ])
            trug_paths = [
                root / "FOLDER_A" / "folder.trug.json",
                root / "FOLDER_B" / "folder.trug.json",
            ]
            folders = _load_folder_trugs(trug_paths, root)
            assert "folder_a" in folders
            assert "folder_b" in folders
            assert len(folders) == 2

    def test_excludes_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create root folder.trug.json
            _make_file(root, "folder.trug.json", json.dumps(
                _minimal_folder_trug("ROOT"), indent=2
            ))
            # Create subfolder
            sub = root / "SUB"
            sub.mkdir()
            _make_file(sub, "folder.trug.json", json.dumps(
                _minimal_folder_trug("SUB"), indent=2
            ))
            trug_paths = [
                root / "folder.trug.json",
                sub / "folder.trug.json",
            ]
            folders = _load_folder_trugs(trug_paths, root)
            assert "sub" in folders
            assert len(folders) == 1  # root excluded


# ===========================================================================
# Unit Tests: Resolve cross-folder edges
# ===========================================================================

class TestResolveCrossFolderEdges:
    def test_resolve_valid(self):
        folders = {
            "folder_a": FolderInfo(
                path=Path("/tmp/a/folder.trug.json"),
                alias="folder_a",
                trug={
                    "nodes": [{"id": "comp_a", "type": "COMPONENT"}],
                    "edges": [
                        {
                            "from_id": "comp_a",
                            "to_id": "folder_b:comp_b",
                            "relation": "uses",
                            "weight": 0.8,
                        }
                    ],
                },
                folder_node=None,
                node_ids={"comp_a"},
            ),
            "folder_b": FolderInfo(
                path=Path("/tmp/b/folder.trug.json"),
                alias="folder_b",
                trug={"nodes": [{"id": "comp_b", "type": "COMPONENT"}], "edges": []},
                folder_node=None,
                node_ids={"comp_b"},
            ),
        }
        resolved, unresolved = _resolve_cross_folder_edges(folders)
        assert len(resolved) == 1
        assert len(unresolved) == 0
        assert resolved[0]["relation"] == "uses"
        assert resolved[0]["source_folder"] == "folder_a"
        assert resolved[0]["target_folder"] == "folder_b"

    def test_resolve_missing_folder(self):
        folders = {
            "folder_a": FolderInfo(
                path=Path("/tmp/a/folder.trug.json"),
                alias="folder_a",
                trug={
                    "nodes": [{"id": "comp_a", "type": "COMPONENT"}],
                    "edges": [
                        {
                            "from_id": "comp_a",
                            "to_id": "nonexistent:comp_x",
                            "relation": "uses",
                            "weight": 1.0,
                        }
                    ],
                },
                folder_node=None,
                node_ids={"comp_a"},
            ),
        }
        resolved, unresolved = _resolve_cross_folder_edges(folders)
        assert len(resolved) == 0
        assert len(unresolved) == 1
        assert "not found" in unresolved[0]["reason"]

    def test_resolve_missing_node(self):
        folders = {
            "folder_a": FolderInfo(
                path=Path("/tmp/a/folder.trug.json"),
                alias="folder_a",
                trug={
                    "nodes": [{"id": "comp_a", "type": "COMPONENT"}],
                    "edges": [
                        {
                            "from_id": "comp_a",
                            "to_id": "folder_b:nonexistent_node",
                            "relation": "uses",
                            "weight": 1.0,
                        }
                    ],
                },
                folder_node=None,
                node_ids={"comp_a"},
            ),
            "folder_b": FolderInfo(
                path=Path("/tmp/b/folder.trug.json"),
                alias="folder_b",
                trug={"nodes": [{"id": "comp_b", "type": "COMPONENT"}], "edges": []},
                folder_node=None,
                node_ids={"comp_b"},
            ),
        }
        resolved, unresolved = _resolve_cross_folder_edges(folders)
        assert len(resolved) == 0
        assert len(unresolved) == 1

    def test_internal_edges_skipped(self):
        folders = {
            "folder_a": FolderInfo(
                path=Path("/tmp/a/folder.trug.json"),
                alias="folder_a",
                trug={
                    "nodes": [{"id": "comp_a"}, {"id": "doc_a"}],
                    "edges": [
                        {
                            "from_id": "comp_a",
                            "to_id": "doc_a",
                            "relation": "contains",
                            "weight": 1.0,
                        }
                    ],
                },
                folder_node=None,
                node_ids={"comp_a", "doc_a"},
            ),
        }
        resolved, unresolved = _resolve_cross_folder_edges(folders)
        assert len(resolved) == 0
        assert len(unresolved) == 0

    def test_case_insensitive_alias(self):
        """Cross-folder refs with uppercase aliases should resolve."""
        folders = {
            "folder_a": FolderInfo(
                path=Path("/tmp/a/folder.trug.json"),
                alias="folder_a",
                trug={
                    "nodes": [{"id": "comp_a", "type": "COMPONENT"}],
                    "edges": [
                        {
                            "from_id": "comp_a",
                            "to_id": "FOLDER_B:comp_b",
                            "relation": "uses",
                            "weight": 0.8,
                        }
                    ],
                },
                folder_node=None,
                node_ids={"comp_a"},
            ),
            "folder_b": FolderInfo(
                path=Path("/tmp/b/folder.trug.json"),
                alias="folder_b",
                trug={"nodes": [{"id": "comp_b", "type": "COMPONENT"}], "edges": []},
                folder_node=None,
                node_ids={"comp_b"},
            ),
        }
        resolved, unresolved = _resolve_cross_folder_edges(folders)
        assert len(resolved) == 1
        assert len(unresolved) == 0

    def test_resolve_missing_source_folder(self):
        """Cross-folder from_id where the source folder doesn't exist."""
        folders = {
            "folder_a": FolderInfo(
                path=Path("/tmp/a/folder.trug.json"),
                alias="folder_a",
                trug={
                    "nodes": [{"id": "comp_a", "type": "COMPONENT"}],
                    "edges": [
                        {
                            "from_id": "nonexistent:comp_x",
                            "to_id": "comp_a",
                            "relation": "uses",
                            "weight": 1.0,
                        }
                    ],
                },
                folder_node=None,
                node_ids={"comp_a"},
            ),
        }
        resolved, unresolved = _resolve_cross_folder_edges(folders)
        assert len(resolved) == 0
        assert len(unresolved) == 1
        assert "source" in unresolved[0]["reason"]

    def test_resolve_missing_source_node(self):
        """Cross-folder from_id where source folder exists but node doesn't."""
        folders = {
            "folder_a": FolderInfo(
                path=Path("/tmp/a/folder.trug.json"),
                alias="folder_a",
                trug={
                    "nodes": [{"id": "comp_a", "type": "COMPONENT"}],
                    "edges": [
                        {
                            "from_id": "folder_b:nonexistent_node",
                            "to_id": "comp_a",
                            "relation": "uses",
                            "weight": 1.0,
                        }
                    ],
                },
                folder_node=None,
                node_ids={"comp_a"},
            ),
            "folder_b": FolderInfo(
                path=Path("/tmp/b/folder.trug.json"),
                alias="folder_b",
                trug={"nodes": [{"id": "comp_b", "type": "COMPONENT"}], "edges": []},
                folder_node=None,
                node_ids={"comp_b"},
            ),
        }
        resolved, unresolved = _resolve_cross_folder_edges(folders)
        assert len(resolved) == 0
        assert len(unresolved) == 1
        assert "source" in unresolved[0]["reason"]

    def test_cross_folder_from_id(self):
        """Cross-folder reference in from_id."""
        folders = {
            "folder_a": FolderInfo(
                path=Path("/tmp/a/folder.trug.json"),
                alias="folder_a",
                trug={
                    "nodes": [{"id": "comp_a", "type": "COMPONENT"}],
                    "edges": [
                        {
                            "from_id": "folder_b:comp_b",
                            "to_id": "comp_a",
                            "relation": "uses",
                            "weight": 1.0,
                        }
                    ],
                },
                folder_node=None,
                node_ids={"comp_a"},
            ),
            "folder_b": FolderInfo(
                path=Path("/tmp/b/folder.trug.json"),
                alias="folder_b",
                trug={"nodes": [{"id": "comp_b", "type": "COMPONENT"}], "edges": []},
                folder_node=None,
                node_ids={"comp_b"},
            ),
        }
        resolved, unresolved = _resolve_cross_folder_edges(folders)
        assert len(resolved) == 1
        assert resolved[0]["source_folder"] == "folder_b"
        assert resolved[0]["target_folder"] == "folder_a"


# ===========================================================================
# Unit Tests: Orphan detection
# ===========================================================================

class TestOrphanDetection:
    _stub = FolderInfo(path=Path("/tmp"), alias="", trug={}, folder_node=None, node_ids=set())

    def test_detects_orphan(self):
        folders = {"a": self._stub, "b": self._stub, "c": self._stub}
        resolved = [
            {"source_folder": "a", "target_folder": "b"},
        ]
        orphans = _find_orphaned_folders(folders, resolved)
        assert orphans == ["c"]

    def test_no_orphans(self):
        folders = {"a": self._stub, "b": self._stub}
        resolved = [
            {"source_folder": "a", "target_folder": "b"},
        ]
        orphans = _find_orphaned_folders(folders, resolved)
        assert orphans == []

    def test_all_orphans(self):
        folders = {"a": self._stub, "b": self._stub}
        orphans = _find_orphaned_folders(folders, [])
        assert orphans == ["a", "b"]


# ===========================================================================
# Unit Tests: Build root graph
# ===========================================================================

class TestBuildRootGraph:
    def _make_folders(self):
        return {
            "folder_a": FolderInfo(
                path=Path("/tmp/FOLDER_A/folder.trug.json"),
                alias="folder_a",
                trug=_minimal_folder_trug("FOLDER_A"),
                folder_node=_minimal_folder_trug("FOLDER_A")["nodes"][0],
                node_ids={"folder_a_folder", "doc_readme"},
            ),
            "folder_b": FolderInfo(
                path=Path("/tmp/FOLDER_B/folder.trug.json"),
                alias="folder_b",
                trug=_minimal_folder_trug("FOLDER_B"),
                folder_node=_minimal_folder_trug("FOLDER_B")["nodes"][0],
                node_ids={"folder_b_folder", "doc_readme"},
            ),
        }

    def test_structure(self):
        folders = self._make_folders()
        graph = _build_root_graph(folders, [], "TEST_REPO")
        assert graph["name"] == "TEST_REPO Root"
        assert graph["type"] == "PROJECT"
        assert len(graph["nodes"]) == 3  # root + 2 folders
        assert graph["nodes"][0]["id"] == "root_folder"
        assert graph["nodes"][0]["type"] == "FOLDER"

    def test_contains_edges(self):
        folders = self._make_folders()
        graph = _build_root_graph(folders, [], "TEST_REPO")
        contains = [e for e in graph["edges"] if e["relation"] == "contains"]
        assert len(contains) == 2

    def test_cross_folder_edges(self):
        folders = self._make_folders()
        resolved = [{
            "source_folder": "folder_a",
            "target_folder": "folder_b",
            "relation": "uses",
            "weight": 0.8,
        }]
        graph = _build_root_graph(folders, resolved, "TEST_REPO")
        uses_edges = [e for e in graph["edges"] if e["relation"] == "uses"]
        assert len(uses_edges) == 1
        assert uses_edges[0]["from_id"] == "folder_folder_a"
        assert uses_edges[0]["to_id"] == "folder_folder_b"

    def test_dedup_cross_folder_edges(self):
        folders = self._make_folders()
        resolved = [
            {
                "source_folder": "folder_a",
                "target_folder": "folder_b",
                "relation": "uses",
                "weight": 0.8,
            },
            {
                "source_folder": "folder_a",
                "target_folder": "folder_b",
                "relation": "uses",
                "weight": 0.9,
            },
        ]
        graph = _build_root_graph(folders, resolved, "TEST_REPO")
        uses_edges = [e for e in graph["edges"] if e["relation"] == "uses"]
        assert len(uses_edges) == 1

    def test_deterministic_output(self):
        folders = self._make_folders()
        g1 = _build_root_graph(folders, [], "TEST_REPO")
        g2 = _build_root_graph(folders, [], "TEST_REPO")
        assert json.dumps(g1, sort_keys=True) == json.dumps(g2, sort_keys=True)

    def test_folder_properties_from_folder_node(self):
        folders = self._make_folders()
        graph = _build_root_graph(folders, [], "TEST_REPO")
        # Find the FOLDER_A node
        fa_node = next(n for n in graph["nodes"] if n["id"] == "folder_folder_a")
        assert fa_node["properties"]["purpose"] == "FOLDER_A project folder"
        assert fa_node["properties"]["phase"] == "CODING"

    def test_edges_sorted(self):
        folders = self._make_folders()
        resolved = [{
            "source_folder": "folder_a",
            "target_folder": "folder_b",
            "relation": "uses",
            "weight": 0.8,
        }]
        graph = _build_root_graph(folders, resolved, "TEST_REPO")
        edge_keys = [(e["relation"], e["from_id"], e["to_id"]) for e in graph["edges"]]
        assert edge_keys == sorted(edge_keys)


# ===========================================================================
# Unit Tests: Make folder node
# ===========================================================================

class TestMakeFolderNode:
    def test_with_folder_node(self):
        info = FolderInfo(
            path=Path("/tmp/MY_FOLDER/folder.trug.json"),
            alias="my_folder",
            trug=_minimal_folder_trug("MY_FOLDER"),
            folder_node=_minimal_folder_trug("MY_FOLDER")["nodes"][0],
            node_ids=set(),
        )
        node = _make_folder_node("my_folder", info)
        assert node["id"] == "folder_my_folder"
        assert node["type"] == "COMPONENT"
        assert node["properties"]["name"] == "MY_FOLDER"
        assert node["properties"]["purpose"] == "MY_FOLDER project folder"
        assert node["parent_id"] == "root_folder"

    def test_without_folder_node(self):
        info = FolderInfo(
            path=Path("/tmp/MY_FOLDER/folder.trug.json"),
            alias="my_folder",
            trug={"nodes": []},
            folder_node=None,
            node_ids=set(),
        )
        node = _make_folder_node("my_folder", info)
        assert node["properties"]["purpose"] == "MY_FOLDER subfolder"


# ===========================================================================
# Integration Tests: map_folder_trugs
# ===========================================================================

class TestMapFolderTrugs:
    def test_basic_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
                {"name": "FOLDER_B"},
            ])
            result = map_folder_trugs(root, dry_run=True)
            assert result.folder_count == 2
            assert result.root_graph is not None
            assert len(result.root_graph["nodes"]) == 3  # root + 2

    def test_with_cross_folder_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {
                    "name": "FOLDER_A",
                    "extra_nodes": [
                        {"id": "comp_a", "type": "COMPONENT",
                         "properties": {"name": "comp_a"}, "parent_id": "folder_a_folder",
                         "contains": [], "metric_level": "DEKA_COMPONENT",
                         "dimension": "folder_structure"},
                    ],
                    "extra_edges": [
                        {"from_id": "comp_a", "to_id": "folder_b:comp_b",
                         "relation": "uses", "weight": 0.8},
                    ],
                },
                {
                    "name": "FOLDER_B",
                    "extra_nodes": [
                        {"id": "comp_b", "type": "COMPONENT",
                         "properties": {"name": "comp_b"}, "parent_id": "folder_b_folder",
                         "contains": [], "metric_level": "DEKA_COMPONENT",
                         "dimension": "folder_structure"},
                    ],
                },
            ])
            result = map_folder_trugs(root, dry_run=True)
            assert len(result.resolved_edges) == 1
            assert len(result.unresolved_edges) == 0
            uses = [e for e in result.root_graph["edges"] if e["relation"] == "uses"]
            assert len(uses) == 1

    def test_with_unresolved_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {
                    "name": "FOLDER_A",
                    "extra_edges": [
                        {"from_id": "doc_readme", "to_id": "nonexistent:comp_x",
                         "relation": "uses", "weight": 1.0},
                    ],
                },
            ])
            result = map_folder_trugs(root, dry_run=True)
            assert len(result.unresolved_edges) == 1

    def test_orphan_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
                {"name": "FOLDER_B"},
                {"name": "FOLDER_C"},
            ])
            result = map_folder_trugs(root, dry_run=True)
            # No cross-folder edges — all are orphans
            assert len(result.orphaned_folders) == 3

    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
            ])
            result = map_folder_trugs(root, dry_run=False)
            output_file = root / "folder.trug.json"
            assert output_file.exists()
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert data["type"] == "PROJECT"
            assert len(data["nodes"]) == 2  # root + 1 folder

    def test_writes_to_custom_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
            ])
            custom_path = root / "custom_root.json"
            result = map_folder_trugs(root, dry_run=False, output=custom_path)
            assert custom_path.exists()
            # Default path should not exist
            assert not (root / "folder.trug.json").exists()

    def test_dry_run_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
            ])
            result = map_folder_trugs(root, dry_run=True)
            assert not (root / "folder.trug.json").exists()

    def test_not_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "not_a_dir"
            with pytest.raises(NotADirectoryError):
                map_folder_trugs(fake)

    def test_no_trugs_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(FileNotFoundError):
                map_folder_trugs(tmp)

    def test_excludes_root_trug(self):
        """Root folder.trug.json should not appear as a subfolder node."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "SUB_A"},
            ])
            # Create a root folder.trug.json
            _make_file(root, "folder.trug.json", json.dumps(
                _minimal_folder_trug("ROOT"), indent=2
            ))
            result = map_folder_trugs(root, dry_run=True)
            assert result.folder_count == 1
            node_ids = [n["id"] for n in result.root_graph["nodes"]]
            assert "folder_sub_a" in node_ids

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
                {"name": "FOLDER_B"},
            ])
            r1 = map_folder_trugs(root, dry_run=True)
            r2 = map_folder_trugs(root, dry_run=True)
            j1 = json.dumps(r1.root_graph, sort_keys=True)
            j2 = json.dumps(r2.root_graph, sort_keys=True)
            assert j1 == j2

    def test_no_subfolder_trugs(self):
        """Root has folder.trug.json but no subfolders do."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_file(root, "folder.trug.json", json.dumps(
                _minimal_folder_trug("ROOT"), indent=2
            ))
            with pytest.raises(FileNotFoundError):
                map_folder_trugs(root)


# ===========================================================================
# MapResult Tests
# ===========================================================================

class TestMapResult:
    def test_edge_count(self):
        r = MapResult()
        r.resolved_edges = [{"a": 1}, {"b": 2}]
        assert r.edge_count == 2

    def test_edge_count_empty(self):
        r = MapResult()
        assert r.edge_count == 0


# ===========================================================================
# CLI Tests
# ===========================================================================

class TestFolderMapCLI:
    def test_cli_dry_run(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
            ])
            exit_code = folder_map_command([str(root), "--dry-run"])
            assert exit_code == 0
            captured = capsys.readouterr()
            # Should print JSON to stdout
            data = json.loads(captured.out)
            assert data["type"] == "PROJECT"

    def test_cli_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
            ])
            exit_code = folder_map_command([str(root)])
            assert exit_code == 0
            assert (root / "folder.trug.json").exists()

    def test_cli_custom_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
            ])
            out_file = root / "custom.json"
            exit_code = folder_map_command([str(root), "--output", str(out_file)])
            assert exit_code == 0
            assert out_file.exists()

    def test_cli_no_trugs(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            exit_code = folder_map_command([tmp])
            assert exit_code == 1

    def test_cli_not_a_directory(self, capsys):
        exit_code = folder_map_command(["/nonexistent/path"])
        assert exit_code == 1

    def test_cli_changes_reported(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            root = _setup_repo(tmp, [
                {"name": "FOLDER_A"},
                {"name": "FOLDER_B"},
            ])
            exit_code = folder_map_command([str(root), "--dry-run"])
            assert exit_code == 0
            captured = capsys.readouterr()
            # Changes go to stderr
            assert "Mapped 2 folder TRUGs" in captured.err
