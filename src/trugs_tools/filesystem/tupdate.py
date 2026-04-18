"""tupdate - Update properties on an existing node in a TRUG graph.

Supports setting individual properties, changing type, and re-parenting.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from trugs_tools.filesystem.utils import (
    get_node_by_id,
    load_graph,
    save_graph,
)


def _parse_value(value_str: str) -> Any:
    """Infer type from string value.

    - "true"/"false" -> bool
    - Numeric strings -> int or float
    - Everything else -> str
    """
    if value_str.lower() == "true":
        return True
    if value_str.lower() == "false":
        return False
    try:
        if "." in value_str:
            return float(value_str)
        return int(value_str)
    except ValueError:
        return value_str


def _set_nested(d: Dict[str, Any], key: str, value: Any) -> None:
    """Set a value using dot notation (e.g., 'metadata.source')."""
    parts = key.split(".")
    for part in parts[:-1]:
        if part not in d or not isinstance(d[part], dict):
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value


# AGENT claude SHALL DEFINE FUNCTION tupdate.
def tupdate(
    directory: Union[str, Path],
    node_id: str,
    set_values: Optional[List[str]] = None,
    node_type: Optional[str] = None,
    parent_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Update properties on an existing node.

    Args:
        directory: Directory containing folder.trug.json
        node_id: ID of node to update
        set_values: List of "key=value" strings for properties
        node_type: New node type (optional)
        parent_id: New parent ID (optional)
        dry_run: If True, show changes without writing

    Returns:
        Dict with 'changes' list and 'node' dict

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If node not found or invalid key=value format
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    node = get_node_by_id(trug, node_id)
    if node is None:
        raise ValueError(f"Node not found: {node_id}")

    changes = []

    if node_type is not None:
        old = node.get("type", "")
        node["type"] = node_type
        changes.append(f"type: {old} -> {node_type}")

    if parent_id is not None:
        old = node.get("parent_id")
        # Validate new parent exists (unless setting to None)
        if parent_id != "null" and get_node_by_id(trug, parent_id) is None:
            raise ValueError(f"Parent node not found: {parent_id}")
        new_parent = None if parent_id == "null" else parent_id

        # Update old parent's contains
        if old is not None:
            old_parent = get_node_by_id(trug, old)
            if old_parent and node_id in old_parent.get("contains", []):
                old_parent["contains"].remove(node_id)

        # Update new parent's contains
        if new_parent is not None:
            new_parent_node = get_node_by_id(trug, new_parent)
            if new_parent_node:
                if "contains" not in new_parent_node:
                    new_parent_node["contains"] = []
                if node_id not in new_parent_node["contains"]:
                    new_parent_node["contains"].append(node_id)

        node["parent_id"] = new_parent
        changes.append(f"parent_id: {old} -> {new_parent}")

    if set_values:
        if "properties" not in node:
            node["properties"] = {}

        for kv in set_values:
            if "=" not in kv:
                raise ValueError(f"Invalid key=value format: {kv}")
            key, value_str = kv.split("=", 1)
            key = key.strip()
            value_str = value_str.strip()

            # Strip surrounding quotes
            if len(value_str) >= 2 and value_str[0] == value_str[-1] and value_str[0] in ('"', "'"):
                value = value_str[1:-1]
            else:
                value = _parse_value(value_str)

            # Get old value for diff
            parts = key.split(".")
            old_val = node["properties"]
            for p in parts:
                if isinstance(old_val, dict):
                    old_val = old_val.get(p)
                else:
                    old_val = None
                    break

            _set_nested(node["properties"], key, value)
            changes.append(f"properties.{key}: {old_val} -> {value}")

    if not changes:
        raise ValueError("No changes specified. Use --set, --type, or --parent.")

    if not dry_run:
        save_graph(dirpath, trug)

    return {"changes": changes, "node": dict(node), "dry_run": dry_run}
