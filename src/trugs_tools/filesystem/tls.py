"""tls - List directory contents with graph enrichment.

Displays files with their TRUG metadata: node type, edge count, dimensions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    get_children,
    get_edges_for_node,
    get_root_node,
    get_node_by_id,
    load_graph,
)


# AGENT claude SHALL DEFINE FUNCTION tls.
def tls(
    directory: Union[str, Path],
    node_id: Optional[str] = None,
    show_edges: bool = False,
    format: str = "text",
) -> Union[str, List[Dict[str, Any]]]:
    """List directory contents with graph metadata.

    Args:
        directory: Directory containing folder.trug.json
        node_id: Node to list children of (default: root)
        show_edges: If True, include edge details
        format: Output format ('text' or 'json')

    Returns:
        Formatted listing string (text) or list of dicts (json)

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    if node_id:
        parent = get_node_by_id(trug, node_id)
        if parent is None:
            raise ValueError(f"Node not found: {node_id}")
    else:
        parent = get_root_node(trug)
        if parent is None:
            raise ValueError("No root node found in TRUG")

    children = get_children(trug, parent["id"])

    if format == "json":
        result = []
        for child in children:
            edges = get_edges_for_node(trug, child["id"])
            entry = {
                "id": child["id"],
                "type": child.get("type", ""),
                "name": child.get("properties", {}).get("name", child["id"]),
                "metric_level": child.get("metric_level", ""),
                "edge_count": len(edges),
                "dimension": child.get("dimension", ""),
            }
            if show_edges:
                entry["edges"] = [
                    {
                        "relation": e.get("relation", ""),
                        "from_id": e.get("from_id", ""),
                        "to_id": e.get("to_id", ""),
                    }
                    for e in edges
                ]
            result.append(entry)
        return result

    # Text format
    lines = []
    header = f"Contents of: {parent.get('properties', {}).get('name', parent['id'])}"
    lines.append(header)
    lines.append("=" * len(header))

    if not children:
        lines.append("  (empty)")
        return "\n".join(lines)

    for child in children:
        edges = get_edges_for_node(trug, child["id"])
        name = child.get("properties", {}).get("name", child["id"])
        ntype = child.get("type", "?")
        edge_count = len(edges)
        dim = child.get("dimension", "")

        line = f"  [{ntype:14s}] {name}"
        if edge_count > 0:
            line += f"  ({edge_count} edge{'s' if edge_count != 1 else ''})"
        if dim:
            line += f"  dim={dim}"
        lines.append(line)

        if show_edges and edges:
            for e in edges:
                rel = e.get("relation", "?")
                from_id = e.get("from_id", "?")
                to_id = e.get("to_id", "?")
                lines.append(f"    └─ {from_id} --[{rel}]--> {to_id}")

    return "\n".join(lines)
