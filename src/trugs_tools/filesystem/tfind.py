"""tfind - Graph query engine for TRUG nodes.

Filters nodes by type, branch, edge type, dimensions, and name patterns.
"""

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    get_edges_for_node,
    load_graph,
)


def tfind(
    directory: Union[str, Path],
    node_type: Optional[str] = None,
    name_pattern: Optional[str] = None,
    dimension: Optional[str] = None,
    edge_relation: Optional[str] = None,
    metric_level: Optional[str] = None,
    has_children: Optional[bool] = None,
    custom_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    format: str = "text",
) -> Union[str, List[Dict[str, Any]]]:
    """Query nodes in a TRUG graph.

    Args:
        directory: Directory containing folder.trug.json
        node_type: Filter by node type (e.g., "SOURCE", "DOCUMENT")
        name_pattern: Regex pattern to match node names
        dimension: Filter by dimension name
        edge_relation: Filter to nodes with edges of this relation
        metric_level: Filter by metric level
        has_children: Filter by whether node has children
        custom_filter: Custom predicate function
        format: Output format ('text' or 'json')

    Returns:
        Formatted results string (text) or list of dicts (json)

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    matches = []

    for node in trug.get("nodes", []):
        if not _matches(trug, node, node_type, name_pattern, dimension,
                        edge_relation, metric_level, has_children,
                        custom_filter):
            continue

        edges = get_edges_for_node(trug, node["id"])
        matches.append({
            "id": node["id"],
            "type": node.get("type", ""),
            "name": node.get("properties", {}).get("name", node["id"]),
            "metric_level": node.get("metric_level", ""),
            "dimension": node.get("dimension", ""),
            "parent_id": node.get("parent_id"),
            "edge_count": len(edges),
            "contains": node.get("contains", []),
        })

    if format == "json":
        return matches

    # Text output
    lines = [f"Found {len(matches)} node(s):"]
    for m in matches:
        line = f"  [{m['type']:14s}] {m['name']} (id={m['id']})"
        if m["edge_count"] > 0:
            line += f"  edges={m['edge_count']}"
        lines.append(line)
    return "\n".join(lines)


def _matches(
    trug: Dict[str, Any],
    node: Dict[str, Any],
    node_type: Optional[str],
    name_pattern: Optional[str],
    dimension: Optional[str],
    edge_relation: Optional[str],
    metric_level: Optional[str],
    has_children: Optional[bool],
    custom_filter: Optional[Callable[[Dict[str, Any]], bool]],
) -> bool:
    """Check if a node matches all provided filters."""
    if node_type and node.get("type") != node_type:
        return False

    if name_pattern:
        name = node.get("properties", {}).get("name", node.get("id", ""))
        if not re.search(name_pattern, name):
            return False

    if dimension and node.get("dimension") != dimension:
        return False

    if metric_level and node.get("metric_level") != metric_level:
        return False

    if has_children is not None:
        children = node.get("contains", [])
        if has_children and not children:
            return False
        if not has_children and children:
            return False

    if edge_relation:
        edges = get_edges_for_node(trug, node["id"])
        relations = {e.get("relation") for e in edges}
        if edge_relation not in relations:
            return False

    if custom_filter and not custom_filter(node):
        return False

    return True
