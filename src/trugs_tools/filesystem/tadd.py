"""tadd - Add files or directories to a TRUG graph.

Adds nodes to folder.trug.json for specified files, inferring node type
from file extension.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    get_node_by_id,
    get_root_node,
    infer_node_type,
    load_graph,
    make_node_id,
    save_graph,
)


# AGENT claude SHALL DEFINE FUNCTION tadd.
def tadd(
    directory: Union[str, Path],
    files: List[str],
    node_type: Optional[str] = None,
    parent_id: Optional[str] = None,
    purpose: str = "",
) -> Dict[str, Any]:
    """Add files to the TRUG graph.

    Args:
        directory: Directory containing folder.trug.json
        files: List of filenames to add
        node_type: Override inferred node type
        parent_id: Parent node ID (default: root node)
        purpose: Purpose description for added nodes

    Returns:
        Updated TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If a file is already in the graph
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    root = get_root_node(trug)
    if root is None:
        raise ValueError("No root node found in TRUG")

    target_parent_id = parent_id or root["id"]
    parent_node = get_node_by_id(trug, target_parent_id)
    if parent_node is None:
        raise ValueError(f"Parent node not found: {target_parent_id}")

    added = []
    for filename in files:
        node_id = make_node_id(filename)

        # Check for duplicate
        if get_node_by_id(trug, node_id) is not None:
            raise ValueError(f"Node already exists: {node_id} (from {filename})")

        filepath = dirpath / filename
        ntype = node_type or (
            "FOLDER" if filepath.is_dir() else infer_node_type(filepath)
        )
        metric = "KILO_FOLDER" if ntype == "FOLDER" else f"BASE_{ntype}"

        node: Dict[str, Any] = {
            "id": node_id,
            "type": ntype,
            "properties": {
                "name": filename,
                "purpose": purpose or f"{'Directory' if filepath.is_dir() else 'File'}: {filename}",
            },
            "parent_id": target_parent_id,
            "contains": [],
            "metric_level": metric,
            "dimension": "folder_structure",
        }
        trug["nodes"].append(node)
        if "contains" not in parent_node:
            parent_node["contains"] = []
        parent_node["contains"].append(node_id)
        added.append(node_id)

    save_graph(dirpath, trug)
    return trug
