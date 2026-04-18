"""TRUGS branch schema loader and validator.

Provides functions to load, list, and validate TRUG branch schemas.
All schemas are loaded from JSON files in this directory.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

_SCHEMA_DIR = Path(__file__).parent

# Cache for loaded schemas (thread-safe via _schema_lock)
_schema_cache: dict[str, dict] = {}
_schema_lock = threading.Lock()


def _load_all_branch_schemas() -> dict[str, dict]:
    """Load all branch schema JSON files and cache them."""
    if _schema_cache:
        return _schema_cache
    with _schema_lock:
        if _schema_cache:
            return _schema_cache
        loaded: dict[str, dict] = {}
        for path in _SCHEMA_DIR.glob("*.schema.json"):
            name = path.name
            if name == "core.schema.json":
                continue
            branch_name = name.replace(".schema.json", "")
            with open(path, "r", encoding="utf-8") as f:
                loaded[branch_name] = json.load(f)
        _schema_cache.update(loaded)
    return _schema_cache


def load_branch_schema(branch: str) -> dict:
    """Load a branch schema by name.

    Args:
        branch: Branch name (e.g. "web", "writer", "knowledge").

    Returns:
        The schema dict for the given branch.

    Raises:
        ValueError: If the branch name is not found.
    """
    schemas = _load_all_branch_schemas()
    key = branch.lower()
    if key not in schemas:
        available = ", ".join(sorted(schemas.keys()))
        raise ValueError(
            f"Unknown branch '{branch}'. Available branches: {available}"
        )
    return schemas[key]


def list_branch_schemas() -> list[str]:
    """Return a sorted list of all available branch names."""
    schemas = _load_all_branch_schemas()
    return sorted(schemas.keys())


def get_branch_node_types(branch: str) -> list[str]:
    """Return valid node types for a branch.

    Args:
        branch: Branch name.

    Returns:
        List of valid node type strings.

    Raises:
        ValueError: If the branch name is not found.
    """
    schema = load_branch_schema(branch)
    return list(schema.get("node_types", []))


def get_branch_relations(branch: str) -> list[str]:
    """Return valid edge relations for a branch.

    Args:
        branch: Branch name.

    Returns:
        List of valid relation strings.

    Raises:
        ValueError: If the branch name is not found.
    """
    schema = load_branch_schema(branch)
    return list(schema.get("relations", []))


def validate_branch_schema(trug: dict) -> list[str]:
    """Validate a TRUG's nodes/edges against its branch schema.

    Detects the branch from the TRUG's "type" field (lowercase lookup).
    When multiple branches share the same graph type (e.g. CODE),
    all valid node types and relations from those branches are accepted.

    Args:
        trug: A TRUG dict with "type", "nodes", and "edges" fields.

    Returns:
        Empty list if valid, or list of error message strings if invalid.
        Returns empty list for unrecognized graph types.
    """
    errors: list[str] = []

    graph_type = trug.get("type", "")
    if not graph_type:
        return errors

    # Collect all matching branch schemas for this graph type
    schemas = _load_all_branch_schemas()
    matching_branches = []
    for schema in schemas.values():
        if schema.get("graph_type", "").upper() == graph_type.upper():
            matching_branches.append(schema)

    if not matching_branches:
        return errors

    # Aggregate valid node types and relations across all matching branches
    valid_node_types: set[str] = set()
    valid_relations: set[str] = set()
    branch_names: list[str] = []
    for schema in matching_branches:
        valid_node_types.update(schema.get("node_types", []))
        valid_relations.update(schema.get("relations", []))
        branch_names.append(schema.get("branch", "unknown"))

    label = "/".join(sorted(branch_names))

    for node in trug.get("nodes", []):
        node_type = node.get("type", "")
        if node_type and node_type not in valid_node_types:
            errors.append(
                f"Invalid node type '{node_type}' for graph type "
                f"'{graph_type}' (branches: {label}). "
                f"Valid types: {sorted(valid_node_types)}"
            )

    for edge in trug.get("edges", []):
        relation = edge.get("relation", "")
        if relation and relation not in valid_relations:
            errors.append(
                f"Invalid relation '{relation}' for graph type "
                f"'{graph_type}' (branches: {label}). "
                f"Valid relations: {sorted(valid_relations)}"
            )

    return errors
