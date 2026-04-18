"""tget - Read full content of a specific node in a TRUG graph.

Displays all 7 CORE fields and properties, with optional edge listing.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    get_edges_for_node,
    get_node_by_id,
    load_graph,
)


# AGENT claude SHALL DEFINE FUNCTION tget.
def tget(
    directory: Union[str, Path],
    node_id: str,
    show_edges: bool = False,
    format: str = "text",
) -> Union[str, Dict[str, Any]]:
    """Read full content of a specific node.

    Args:
        directory: Directory containing folder.trug.json
        node_id: ID of node to read
        show_edges: If True, also show connected edges
        format: Output format ('text' or 'json')

    Returns:
        Formatted node content string (text) or dict (json)

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If node not found
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    node = get_node_by_id(trug, node_id)
    if node is None:
        raise ValueError(f"Node not found: {node_id}")

    edges = get_edges_for_node(trug, node_id) if show_edges else []

    if format == "json":
        result = dict(node)
        if show_edges:
            result["edges"] = edges
        return result

    # Text format
    lines = [f"Node: {node['id']}"]
    # 7 CORE fields
    lines.append(f"  type: {node.get('type', '')}")
    lines.append(f"  parent_id: {node.get('parent_id')}")
    lines.append(f"  contains: {node.get('contains', [])}")
    lines.append(f"  metric_level: {node.get('metric_level', '')}")
    lines.append(f"  dimension: {node.get('dimension', '')}")

    props = node.get("properties", {})
    if props:
        lines.append("  properties:")
        for key, value in props.items():
            lines.append(f"    {key}: {value}")
    else:
        lines.append("  properties: {}")

    if show_edges and edges:
        lines.append(f"\nEdges ({len(edges)}):")
        for e in edges:
            from_id = e.get("from_id", "?")
            to_id = e.get("to_id", "?")
            relation = e.get("relation", "?")
            lines.append(f"  {from_id} --[{relation}]--> {to_id}")

    return "\n".join(lines)
