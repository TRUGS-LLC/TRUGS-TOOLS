"""Filesystem utilities for TRUGS graph operations.

Provides load_graph, save_graph, validate_graph, and helper functions
used by all filesystem commands.

load_graph and save_graph route through trugs-store dual I/O:
  - When PORT_DSN is set: reads/writes PostgreSQL (source of truth)
  - When PORT_DSN is unset: reads/writes JSON files only
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from trugs_tools.validator import validate_trug
from trugs_tools.errors import ValidationResult


TRUG_FILENAME = "folder.trug.json"
BACKUP_SUFFIX = ".backup"


def load_graph(directory: Union[str, Path]) -> Dict[str, Any]:
    """Load folder.trug.json from a directory.

    When PORT_DSN is set: reads from PostgreSQL. Raises on DB error.
    When PORT_DSN is unset: reads from JSON file.

    Args:
        directory: Path to directory containing folder.trug.json

    Returns:
        Parsed TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist (no-DSN mode)
        KeyError/OperationalError: If DB read fails (DSN mode)
    """
    path = Path(directory) / TRUG_FILENAME
    from trugs_store.persistence.dual_write import read_trug
    try:
        return read_trug(path)
    except FileNotFoundError:
        raise FileNotFoundError(f"No {TRUG_FILENAME} found in {directory}")


def save_graph(directory: Union[str, Path], trug: Dict[str, Any],
               backup: bool = True) -> Path:
    """Save TRUG to folder.trug.json in a directory.

    Writes to PostgreSQL (when PORT_DSN set) and JSON file.
    Backup is created before overwriting if requested.

    Args:
        directory: Target directory
        trug: TRUG dictionary to save
        backup: If True, back up existing file before overwriting

    Returns:
        Path to the written file
    """
    dirpath = Path(directory)
    dirpath.mkdir(parents=True, exist_ok=True)
    target = dirpath / TRUG_FILENAME

    if backup and target.exists():
        backup_path = dirpath / (TRUG_FILENAME + BACKUP_SUFFIX)
        shutil.copy2(target, backup_path)

    from trugs_store.persistence.dual_write import write_trug
    write_trug(trug, target)

    return target


def validate_graph(trug: Dict[str, Any]) -> ValidationResult:
    """Validate a TRUG dictionary.

    Args:
        trug: TRUG dictionary

    Returns:
        ValidationResult with errors and warnings
    """
    return validate_trug(trug)


def get_node_by_id(trug: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    """Find a node by its ID.

    Args:
        trug: TRUG dictionary
        node_id: Node identifier

    Returns:
        Node dictionary or None
    """
    for node in trug.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def get_children(trug: Dict[str, Any], parent_id: str) -> List[Dict[str, Any]]:
    """Get child nodes of a parent, sorted by type then name.

    Args:
        trug: TRUG dictionary
        parent_id: Parent node ID

    Returns:
        Sorted list of child nodes
    """
    children = [
        n for n in trug.get("nodes", [])
        if n.get("parent_id") == parent_id
    ]
    children.sort(
        key=lambda n: (
            n.get("type", ""),
            n.get("properties", {}).get("name", n.get("id", "")),
        )
    )
    return children


def get_edges_for_node(trug: Dict[str, Any], node_id: str) -> List[Dict[str, Any]]:
    """Get all edges involving a node (as source or target).

    Args:
        trug: TRUG dictionary
        node_id: Node identifier

    Returns:
        List of edges involving the node
    """
    return [
        e for e in trug.get("edges", [])
        if e.get("from_id") == node_id or e.get("to_id") == node_id
    ]


def get_root_node(trug: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find the FOLDER root node.

    Args:
        trug: TRUG dictionary

    Returns:
        Root node dictionary or None
    """
    for node in trug.get("nodes", []):
        if node.get("type") == "FOLDER":
            return node
    for node in trug.get("nodes", []):
        if node.get("parent_id") is None:
            return node
    return None


def infer_node_type(filepath: Union[str, Path]) -> str:
    """Infer TRUG node type from file extension.

    Args:
        filepath: Path to file

    Returns:
        Inferred node type string
    """
    ext_map = {
        ".py": "SOURCE",
        ".go": "SOURCE",
        ".rs": "SOURCE",
        ".js": "SOURCE",
        ".ts": "SOURCE",
        ".jsx": "SOURCE",
        ".tsx": "SOURCE",
        ".c": "SOURCE",
        ".cpp": "SOURCE",
        ".h": "SOURCE",
        ".java": "SOURCE",
        ".rb": "SOURCE",
        ".md": "DOCUMENT",
        ".txt": "DOCUMENT",
        ".rst": "DOCUMENT",
        ".json": "CONFIGURATION",
        ".yaml": "CONFIGURATION",
        ".yml": "CONFIGURATION",
        ".toml": "CONFIGURATION",
        ".ini": "CONFIGURATION",
        ".cfg": "CONFIGURATION",
        ".trug.json": "SPECIFICATION",
        ".test.py": "TEST",
        ".test.js": "TEST",
        ".test.ts": "TEST",
        "_test.go": "TEST",
        ".spec.js": "TEST",
        ".spec.ts": "TEST",
    }
    path = Path(filepath)
    name = path.name

    # Check compound extensions first (most specific)
    for ext, node_type in ext_map.items():
        if name.endswith(ext) and "." in ext[1:]:
            return node_type

    # Check simple extension
    suffix = path.suffix.lower()
    return ext_map.get(suffix, "SOURCE")


def make_node_id(name: str) -> str:
    """Generate a node ID from a filename.

    Args:
        name: Filename or identifier

    Returns:
        Sanitized node ID
    """
    return name.replace(".", "_").replace("-", "_").replace(" ", "_").lower()


def create_backup(directory: Union[str, Path]) -> Optional[Path]:
    """Create a backup of folder.trug.json.

    Args:
        directory: Directory containing folder.trug.json

    Returns:
        Path to backup file, or None if no source exists
    """
    source = Path(directory) / TRUG_FILENAME
    if not source.exists():
        return None
    backup_path = Path(directory) / (TRUG_FILENAME + BACKUP_SUFFIX)
    shutil.copy2(source, backup_path)
    return backup_path


def restore_backup(directory: Union[str, Path]) -> bool:
    """Restore folder.trug.json from backup.

    Args:
        directory: Directory containing backup

    Returns:
        True if restored, False if no backup found
    """
    dirpath = Path(directory)
    backup_path = dirpath / (TRUG_FILENAME + BACKUP_SUFFIX)
    target = dirpath / TRUG_FILENAME
    if not backup_path.exists():
        return False
    shutil.copy2(backup_path, target)
    return True
