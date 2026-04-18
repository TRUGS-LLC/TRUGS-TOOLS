"""tcd - Graph-based navigation within a TRUG.

Navigate using node IDs, edge types, or parent/child relationships.
Returns node context information for the target.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    get_children,
    get_edges_for_node,
    get_node_by_id,
    get_root_node,
    load_graph,
)


def tcd(
    directory: Union[str, Path],
    target: str = "",
    current: Optional[str] = None,
) -> Dict[str, Any]:
    """Navigate to a node in the TRUG graph.

    Supports:
      - Node ID:  ``tcd(dir, "my_node_id")``
      - Parent:   ``tcd(dir, "..", current="child_id")``
      - Root:     ``tcd(dir, "/")``

    Args:
        directory: Directory containing folder.trug.json
        target: Target node ID, ".." for parent, "/" for root
        current: Current node ID (needed for ".." navigation)

    Returns:
        Dict with node info, children summary, and edges

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If target node not found
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    # Navigate to root
    if target in ("", "/"):
        node = get_root_node(trug)
        if node is None:
            raise ValueError("No root node found in TRUG")
    # Navigate to parent
    elif target == "..":
        if current is None:
            raise ValueError("Current node required for '..' navigation")
        cur_node = get_node_by_id(trug, current)
        if cur_node is None:
            raise ValueError(f"Current node not found: {current}")
        parent_id = cur_node.get("parent_id")
        if parent_id is None:
            raise ValueError("Already at root node")
        node = get_node_by_id(trug, parent_id)
        if node is None:
            raise ValueError(f"Parent node not found: {parent_id}")
    # Navigate by ID
    else:
        node = get_node_by_id(trug, target)
        if node is None:
            raise ValueError(f"Node not found: {target}")

    children = get_children(trug, node["id"])
    edges = get_edges_for_node(trug, node["id"])

    return {
        "node": node,
        "children": [
            {
                "id": c["id"],
                "type": c.get("type", ""),
                "name": c.get("properties", {}).get("name", c["id"]),
            }
            for c in children
        ],
        "edges": [
            {
                "relation": e.get("relation", ""),
                "from_id": e.get("from_id", ""),
                "to_id": e.get("to_id", ""),
            }
            for e in edges
        ],
        "path": _build_path(trug, node["id"]),
    }


def _build_path(trug: Dict[str, Any], node_id: str) -> str:
    """Build a path string from root to the given node."""
    parts: List[str] = []
    current_id: Optional[str] = node_id
    visited = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        node = get_node_by_id(trug, current_id)
        if node is None:
            break
        name = node.get("properties", {}).get("name", node["id"])
        parts.append(name)
        current_id = node.get("parent_id")
    parts.reverse()
    return "/" + "/".join(parts)
