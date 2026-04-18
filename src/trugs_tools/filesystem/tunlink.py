"""tunlink - Remove specific edges from a TRUG graph.

Supports removal by endpoints, by relation filter, and bulk removal.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    load_graph,
    save_graph,
)


def tunlink(
    directory: Union[str, Path],
    from_id: Optional[str] = None,
    to_id: Optional[str] = None,
    relation: Optional[str] = None,
    remove_all: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Remove edges from a TRUG graph.

    Args:
        directory: Directory containing folder.trug.json
        from_id: Source node ID (required unless --all with --to)
        to_id: Target node ID (required unless --all with --from)
        relation: Edge relation type to filter by
        remove_all: Remove all matching edges (from or to a node)
        dry_run: If True, show what would be removed without writing

    Returns:
        Dict with 'removed_edges' list and 'dry_run' flag

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If no matching edges found or invalid arguments
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    if from_id is None and to_id is None:
        raise ValueError("At least one of --from or --to is required")

    edges = trug.get("edges", [])
    to_remove = []

    for i, e in enumerate(edges):
        match = True

        if from_id is not None and e.get("from_id") != from_id:
            match = False
        if to_id is not None and e.get("to_id") != to_id:
            match = False
        if relation is not None and e.get("relation") != relation:
            match = False

        # If not --all, require both from and to specified
        if not remove_all and (from_id is None or to_id is None):
            match = False

        if match:
            to_remove.append(i)

    if not to_remove:
        parts = []
        if from_id:
            parts.append(f"from={from_id}")
        if to_id:
            parts.append(f"to={to_id}")
        if relation:
            parts.append(f"relation={relation}")
        raise ValueError(f"No matching edge found: {', '.join(parts)}")

    removed_edges = []
    for i in to_remove:
        e = edges[i]
        removed_edges.append(
            f"{e.get('from_id')} --[{e.get('relation', '?')}]--> {e.get('to_id')}"
        )

    if not dry_run:
        trug["edges"] = [e for i, e in enumerate(edges) if i not in to_remove]
        save_graph(dirpath, trug)

    return {
        "removed_edges": removed_edges,
        "dry_run": dry_run,
    }
