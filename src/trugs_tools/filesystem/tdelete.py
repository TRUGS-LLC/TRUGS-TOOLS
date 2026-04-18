"""tdelete - Remove nodes and their connected edges from a TRUG graph.

Cascades: removes the node, all connected edges, and updates parent contains.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    get_edges_for_node,
    get_node_by_id,
    load_graph,
    save_graph,
)


# AGENT claude SHALL DEFINE FUNCTION tdelete.
def tdelete(
    directory: Union[str, Path],
    node_ids: List[str],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Remove nodes and all connected edges from a TRUG graph.

    Args:
        directory: Directory containing folder.trug.json
        node_ids: List of node IDs to delete
        dry_run: If True, show what would be deleted without writing

    Returns:
        Dict with 'deleted_nodes', 'deleted_edges', and 'dry_run' keys

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If any node not found
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    # Validate all nodes exist first
    for node_id in node_ids:
        if get_node_by_id(trug, node_id) is None:
            raise ValueError(f"Node not found: {node_id}")

    deleted_nodes = []
    deleted_edges = []

    for node_id in node_ids:
        node = get_node_by_id(trug, node_id)
        if node is None:
            continue  # Already deleted (overlapping contains)

        # Collect edges to remove
        edges = get_edges_for_node(trug, node_id)
        for e in edges:
            edge_desc = f"{e.get('from_id')} --[{e.get('relation', '?')}]--> {e.get('to_id')}"
            if edge_desc not in deleted_edges:
                deleted_edges.append(edge_desc)

        # Remove from parent's contains
        parent_id = node.get("parent_id")
        if parent_id is not None:
            parent = get_node_by_id(trug, parent_id)
            if parent and node_id in parent.get("contains", []):
                parent["contains"].remove(node_id)

        # Re-parent children to null (orphan, don't cascade by default)
        for child in trug.get("nodes", []):
            if child.get("parent_id") == node_id:
                child["parent_id"] = None

        # Remove connected edges
        trug["edges"] = [
            e for e in trug.get("edges", [])
            if e.get("from_id") != node_id and e.get("to_id") != node_id
        ]

        # Remove the node
        trug["nodes"] = [n for n in trug["nodes"] if n.get("id") != node_id]
        deleted_nodes.append(node_id)

    if not dry_run:
        save_graph(dirpath, trug)

    return {
        "deleted_nodes": deleted_nodes,
        "deleted_edges": deleted_edges,
        "dry_run": dry_run,
    }
