"""tlink - Create typed edges between nodes in a TRUG graph.

Validates edge types and ensures referential integrity.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.filesystem.utils import (
    get_node_by_id,
    load_graph,
    save_graph,
)


# Valid edge relations from TRUGS v1.0 specification
VALID_RELATIONS = {
    "CONTAINS",
    "DEPENDS_ON",
    "IMPLEMENTS",
    "TESTS",
    "DOCUMENTS",
    "GENERATES",
    "REFERENCES",
    "EXTENDS",
    "CONFIGURES",
    "ORCHESTRATES",
    "VALIDATES",
    "RENDERS",
}


def tlink(
    directory: Union[str, Path],
    from_id: str,
    to_id: str,
    relation: str,
    weight: Optional[float] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a typed edge between two nodes.

    Args:
        directory: Directory containing folder.trug.json
        from_id: Source node ID
        to_id: Target node ID
        relation: Edge relation type
        weight: Optional edge weight (0.0-1.0): curator endorsement strength
        properties: Optional edge properties

    Returns:
        Updated TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If nodes not found or relation invalid
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    # Validate nodes exist
    if get_node_by_id(trug, from_id) is None:
        raise ValueError(f"Source node not found: {from_id}")
    if get_node_by_id(trug, to_id) is None:
        raise ValueError(f"Target node not found: {to_id}")

    # Validate relation
    if relation not in VALID_RELATIONS:
        raise ValueError(
            f"Invalid relation: {relation}. "
            f"Valid relations: {', '.join(sorted(VALID_RELATIONS))}"
        )

    # Check for self-reference
    if from_id == to_id:
        raise ValueError("Cannot create edge from a node to itself")

    # Check for duplicate edge
    for edge in trug.get("edges", []):
        if (edge.get("from_id") == from_id and
                edge.get("to_id") == to_id and
                edge.get("relation") == relation):
            raise ValueError(
                f"Edge already exists: {from_id} --[{relation}]--> {to_id}"
            )

    edge: Dict[str, Any] = {
        "from_id": from_id,
        "to_id": to_id,
        "relation": relation,
    }
    if weight is not None:
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight < 0.0 or weight > 1.0:
            raise ValueError(f"Weight must be a number between 0.0 and 1.0, got {weight}")
        edge["weight"] = float(weight)
    if properties:
        edge["properties"] = properties

    trug["edges"].append(edge)
    save_graph(dirpath, trug)
    return trug


def tunlink(
    directory: Union[str, Path],
    from_id: str,
    to_id: str,
    relation: Optional[str] = None,
) -> Dict[str, Any]:
    """Remove an edge between two nodes.

    Args:
        directory: Directory containing folder.trug.json
        from_id: Source node ID
        to_id: Target node ID
        relation: Edge relation type (if None, removes all edges between nodes)

    Returns:
        Updated TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If no matching edge found
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    original_count = len(trug.get("edges", []))

    if relation:
        trug["edges"] = [
            e for e in trug.get("edges", [])
            if not (e.get("from_id") == from_id and
                    e.get("to_id") == to_id and
                    e.get("relation") == relation)
        ]
    else:
        trug["edges"] = [
            e for e in trug.get("edges", [])
            if not (e.get("from_id") == from_id and e.get("to_id") == to_id)
        ]

    if len(trug["edges"]) == original_count:
        raise ValueError(
            f"No matching edge found: {from_id} --> {to_id}"
            + (f" [{relation}]" if relation else "")
        )

    save_graph(dirpath, trug)
    return trug
