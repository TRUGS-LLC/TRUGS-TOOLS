"""Search across all folder.trug.json files for a concept, node, or file."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# AGENT claude SHALL DEFINE FUNCTION twhere.
def twhere(
    query: str,
    root: str = ".",
    search_fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Search all folder.trug.json files for nodes matching a query.

    Args:
        query: Search term (regex supported)
        root: Root directory to search from
        search_fields: Node fields to search (default: id, type, properties.title,
                       properties.name, properties.path, properties.description)

    Returns:
        List of matches, each containing folder, node_id, node_type, match_field,
        match_value, and file_path (if the node references a file)
    """
    if search_fields is None:
        search_fields = [
            "id", "type",
            "properties.title", "properties.name",
            "properties.path", "properties.description",
            "properties.purpose",
        ]

    pattern = re.compile(query, re.IGNORECASE)
    root_path = Path(root).resolve()
    results = []

    # Find all folder.trug.json files
    for trug_path in sorted(root_path.rglob("folder.trug.json")):
        # Skip zzz_ archives
        if any(p.startswith("zzz_") for p in trug_path.parts):
            continue
        # Skip __pycache__ and .git
        if any(p.startswith((".", "__")) for p in trug_path.parts):
            continue

        try:
            with open(trug_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        folder = trug_path.parent.relative_to(root_path)

        for node in data.get("nodes", []):
            for field_path in search_fields:
                value = _get_nested(node, field_path)
                if value is None:
                    continue
                value_str = str(value)
                if pattern.search(value_str):
                    # Try to find file path for this node
                    file_path = _resolve_file_path(node, trug_path.parent)
                    results.append({
                        "folder": str(folder),
                        "node_id": node.get("id", "?"),
                        "node_type": node.get("type", "?"),
                        "match_field": field_path,
                        "match_value": value_str[:100],
                        "file_path": str(file_path) if file_path else None,
                    })
                    break  # One match per node is enough

    return results


def _get_nested(obj: dict, path: str) -> Any:
    """Get a nested value from a dict using dot notation."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _resolve_file_path(node: dict, folder: Path) -> Optional[Path]:
    """Try to resolve the actual file path for a node."""
    props = node.get("properties", {})

    # Check common path fields
    for field in ("path", "file_path", "source_path", "subgraph_ref"):
        val = props.get(field)
        if val:
            candidate = folder / val
            if candidate.exists():
                return candidate

    # Check if node id matches a file
    node_id = node.get("id", "")
    for suffix in ("", ".py", ".md", ".json"):
        candidate = folder / (node_id + suffix)
        if candidate.exists():
            return candidate

    return None
