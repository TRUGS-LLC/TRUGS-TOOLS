"""tdim - Dimension management for TRUG nodes.

Add, remove, and list dimensions on nodes and the graph itself.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    get_node_by_id,
    load_graph,
    save_graph,
)


def tdim_add(
    directory: Union[str, Path],
    name: str,
    description: str = "",
    base_level: str = "BASE",
) -> Dict[str, Any]:
    """Add a dimension to the TRUG graph.

    Args:
        directory: Directory containing folder.trug.json
        name: Dimension name
        description: Dimension description
        base_level: Base metric level for the dimension

    Returns:
        Updated TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If dimension already exists
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    dims = trug.setdefault("dimensions", {})
    if name in dims:
        raise ValueError(f"Dimension already exists: {name}")

    dims[name] = {
        "description": description or f"Dimension: {name}",
        "base_level": base_level,
    }

    save_graph(dirpath, trug)
    return trug


def tdim_remove(
    directory: Union[str, Path],
    name: str,
    force: bool = False,
) -> Dict[str, Any]:
    """Remove a dimension from the TRUG graph.

    Args:
        directory: Directory containing folder.trug.json
        name: Dimension name to remove
        force: If True, also remove dimension from all nodes

    Returns:
        Updated TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If dimension not found, or nodes use it and force=False
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    dims = trug.get("dimensions", {})
    if name not in dims:
        raise ValueError(f"Dimension not found: {name}")

    # Check if any nodes use this dimension
    using = [
        n["id"] for n in trug.get("nodes", [])
        if n.get("dimension") == name
    ]
    if using and not force:
        raise ValueError(
            f"Dimension '{name}' is used by {len(using)} node(s): "
            f"{', '.join(using[:5])}{'...' if len(using) > 5 else ''}. "
            f"Use force=True to remove anyway."
        )

    del dims[name]

    if force:
        for node in trug.get("nodes", []):
            if node.get("dimension") == name:
                node["dimension"] = ""

    save_graph(dirpath, trug)
    return trug


def tdim_list(
    directory: Union[str, Path],
    format: str = "text",
) -> Union[str, Dict[str, Any]]:
    """List dimensions in the TRUG graph.

    Args:
        directory: Directory containing folder.trug.json
        format: Output format ('text' or 'json')

    Returns:
        Formatted listing string (text) or dict (json)

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    dims = trug.get("dimensions", {})

    # Count nodes per dimension
    dim_counts: Dict[str, int] = {}
    for node in trug.get("nodes", []):
        d = node.get("dimension", "")
        if d:
            dim_counts[d] = dim_counts.get(d, 0) + 1

    if format == "json":
        result = {}
        for name, info in sorted(dims.items()):
            result[name] = {
                **info,
                "node_count": dim_counts.get(name, 0),
            }
        return result

    # Text output
    lines = [f"Dimensions ({len(dims)}):"]
    for name, info in sorted(dims.items()):
        count = dim_counts.get(name, 0)
        desc = info.get("description", "")
        base = info.get("base_level", "")
        lines.append(f"  {name}: {desc} (base={base}, nodes={count})")
    return "\n".join(lines)


def tdim_set(
    directory: Union[str, Path],
    node_id: str,
    dimension: str,
) -> Dict[str, Any]:
    """Set the dimension of a node.

    Args:
        directory: Directory containing folder.trug.json
        node_id: Node to update
        dimension: Dimension name to assign

    Returns:
        Updated TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If node or dimension not found
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    node = get_node_by_id(trug, node_id)
    if node is None:
        raise ValueError(f"Node not found: {node_id}")

    dims = trug.get("dimensions", {})
    if dimension and dimension not in dims:
        raise ValueError(f"Dimension not found: {dimension}")

    node["dimension"] = dimension
    save_graph(dirpath, trug)
    return trug


# Convenience wrapper
def tdim(
    directory: Union[str, Path],
    action: str = "list",
    **kwargs,
) -> Any:
    """Dimension management dispatcher.

    Args:
        directory: Directory containing folder.trug.json
        action: One of 'add', 'remove', 'list', 'set'
        **kwargs: Arguments passed to the specific action

    Returns:
        Result from the specific action
    """
    actions = {
        "add": tdim_add,
        "remove": tdim_remove,
        "list": tdim_list,
        "set": tdim_set,
    }
    if action not in actions:
        raise ValueError(f"Unknown action: {action}. Valid: {', '.join(actions)}")
    return actions[action](directory, **kwargs)
