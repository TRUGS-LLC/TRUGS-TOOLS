# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""tinit - Initialize folder.trug.json in a directory.

Creates a valid folder.trug.json with a FOLDER root node and optionally
scans the directory to add existing files as child nodes.

<trl>
PROCESS tinit SHALL BUILD RECORD trug_graph THEN WRITE FILE folder_trug_json TO DATA directory.
</trl>
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union

from trugs_folder.utils import (
    TRUG_FILENAME,
    infer_metric_level,
    infer_node_type,
    make_node_id,
    save_graph,
)


# AGENT claude SHALL DEFINE FUNCTION tinit.
def tinit(
    directory: Union[str, Path],
    name: Optional[str] = None,
    description: str = "",
    scan: bool = False,
    force: bool = False,
    qualifying_interest: Optional[str] = None,
) -> Dict[str, Any]:
    """Initialize a folder.trug.json in the given directory.

    Args:
        directory: Target directory
        name: Project name (default: directory name)
        description: Project description
        scan: If True, scan directory for existing files
        force: If True, overwrite existing folder.trug.json
        qualifying_interest: Hub qualifying interest (what this TRUG curates)

    Returns:
        The created TRUG dictionary

    Raises:
        FileExistsError: If folder.trug.json already exists and force=False

    <trl>
    FUNCTION tinit SHALL BUILD RECORD trug_graph WITH RECORD folder_node THEN WRITE FILE folder_trug_json SUBJECT_TO force OR NOT FILE folder_trug_json EXISTS.
    </trl>
    """
    dirpath = Path(directory).resolve()
    trug_path = dirpath / TRUG_FILENAME

    if trug_path.exists() and not force:
        raise FileExistsError(
            f"{TRUG_FILENAME} already exists in {dirpath}. Use force=True to overwrite."
        )

    folder_name = name or dirpath.name
    root_id = make_node_id(folder_name) + "_folder"

    trug: Dict[str, Any] = {
        "name": f"{folder_name} Folder",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": description or f"TRUG graph for {folder_name}",
        "dimensions": {
            "folder_structure": {
                "description": "Folder contents and their relationships",
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
                "id": root_id,
                "type": "FOLDER",
                "properties": {
                    "name": folder_name,
                    "purpose": description or f"Root folder for {folder_name}",
                    "phase": "ACTIVE",
                    "status": "ACTIVE",
                },
                "parent_id": None,
                "contains": [],
                "metric_level": "KILO_FOLDER",
                "dimension": "folder_structure",
            }
        ],
        "edges": [],
    }

    # Optionally scan directory for existing files
    if scan:
        _scan_directory(dirpath, trug, root_id)

    if qualifying_interest:
        trug["nodes"][0]["properties"]["qualifying_interest"] = qualifying_interest

    save_graph(dirpath, trug, backup=not force)
    return trug


def _scan_directory(dirpath: Path, trug: Dict[str, Any], root_id: str) -> None:
    """Scan directory and add file nodes to the TRUG.

    Ignores hidden files, __pycache__, and the TRUG file itself.
    """
    ignore = {
        TRUG_FILENAME,
        TRUG_FILENAME + ".backup",
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".mypy_cache",
        "htmlcov",
        ".coverage",
    }

    root_node = trug["nodes"][0]
    for item in sorted(dirpath.iterdir()):
        if item.name.startswith(".") or item.name in ignore:
            continue

        node_id = make_node_id(item.name)
        node_type = "FOLDER" if item.is_dir() else infer_node_type(item)
        metric = "KILO_FOLDER" if item.is_dir() else infer_metric_level(node_type)

        node: Dict[str, Any] = {
            "id": node_id,
            "type": node_type,
            "properties": {
                "name": item.name,
                "purpose": f"{'Directory' if item.is_dir() else 'File'}: {item.name}",
            },
            "parent_id": root_id,
            "contains": [],
            "metric_level": metric,
            "dimension": "folder_structure",
        }
        trug["nodes"].append(node)
        root_node["contains"].append(node_id)
        # Bidirectional invariant: every contains-array entry needs its
        # matching 'contains' edge or the graph fails folder_check (#53).
        trug["edges"].append(
            {
                "from_id": root_id,
                "to_id": node_id,
                "relation": "contains",
                "weight": 1.0,
                "properties": {},
            }
        )
