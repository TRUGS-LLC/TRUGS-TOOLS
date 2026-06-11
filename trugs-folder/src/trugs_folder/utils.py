# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Filesystem utilities for TRUGS graph operations.

Provides load_graph, save_graph, validate_graph, and helper functions
used by all filesystem commands.

load_graph and save_graph route through trugs-store dual I/O:
  - When PORT_DSN is set: reads/writes PostgreSQL (source of truth)
  - When PORT_DSN is unset: reads/writes JSON files only

<trl>
PROCESS filesystem_utils SHALL LOAD RECORD trug FROM FILE AND SHALL SAVE RECORD trug TO FILE AND SHALL EXPOSE FUNCTION helper FOR RECORD node AND RECORD edge QUERY.
</trl>
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trugs_tools.validator import validate_trug
from trugs_tools.errors import ValidationResult


TRUG_FILENAME = "folder.trug.json"
BACKUP_SUFFIX = ".backup"


# AGENT claude SHALL DEFINE FUNCTION load_graph.
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

    <trl>
    FUNCTION load_graph SHALL READ FILE folder_trug_json FROM DATA directory THEN RETURN RECORD trug.
    </trl>
    """
    path = Path(directory) / TRUG_FILENAME
    from trugs_store.persistence.dual_write import read_trug

    try:
        return read_trug(path)
    except FileNotFoundError:
        raise FileNotFoundError(f"No {TRUG_FILENAME} found in {directory}")


# AGENT claude SHALL DEFINE FUNCTION save_graph.
def save_graph(
    directory: Union[str, Path], trug: Dict[str, Any], backup: bool = True
) -> Path:
    """Save TRUG to folder.trug.json in a directory.

    Writes to PostgreSQL (when PORT_DSN set) and JSON file.
    Backup is created before overwriting if requested.

    Args:
        directory: Target directory
        trug: TRUG dictionary to save
        backup: If True, back up existing file before overwriting

    Returns:
        Path to the written file

    <trl>
    FUNCTION save_graph SHALL WRITE RECORD trug TO FILE folder_trug_json THEN RETURN DATA path SUBJECT_TO backup SHALL COPY FILE existing BEFORE WRITE.
    </trl>
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


# AGENT claude SHALL DEFINE FUNCTION validate_graph.
def validate_graph(trug: Dict[str, Any]) -> ValidationResult:
    """Validate a TRUG dictionary.

    Args:
        trug: TRUG dictionary

    Returns:
        ValidationResult with errors and warnings

    <trl>
    FUNCTION validate_graph SHALL VALIDATE RECORD trug THEN RETURN RECORD validation_result.
    </trl>
    """
    return validate_trug(trug)


# AGENT claude SHALL DEFINE FUNCTION get_node_by_id.
def get_node_by_id(trug: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    """Find a node by its ID.

    Args:
        trug: TRUG dictionary
        node_id: Node identifier

    Returns:
        Node dictionary or None

    <trl>
    FUNCTION get_node_by_id SHALL SCAN RECORD trug THEN RETURN RECORD node SUBJECT_TO RECORD node id EQUALS DATA node_id.
    </trl>
    """
    for node in trug.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


# AGENT claude SHALL DEFINE FUNCTION get_children.
def get_children(trug: Dict[str, Any], parent_id: str) -> List[Dict[str, Any]]:
    """Get child nodes of a parent, sorted by type then name.

    Args:
        trug: TRUG dictionary
        parent_id: Parent node ID

    Returns:
        Sorted list of child nodes

    <trl>
    FUNCTION get_children SHALL FILTER RECORD trug BY DATA parent_id THEN RETURN DATA sorted_node_list.
    </trl>
    """
    children = [n for n in trug.get("nodes", []) if n.get("parent_id") == parent_id]
    children.sort(
        key=lambda n: (
            n.get("type", ""),
            n.get("properties", {}).get("name", n.get("id", "")),
        )
    )
    return children


# AGENT claude SHALL DEFINE FUNCTION get_edges_for_node.
def get_edges_for_node(trug: Dict[str, Any], node_id: str) -> List[Dict[str, Any]]:
    """Get all edges involving a node (as source or target).

    Args:
        trug: TRUG dictionary
        node_id: Node identifier

    Returns:
        List of edges involving the node

    <trl>
    FUNCTION get_edges_for_node SHALL FILTER RECORD trug BY DATA node_id THEN RETURN DATA edge_list SUBJECT_TO RECORD edge from_id OR to_id EQUALS DATA node_id.
    </trl>
    """
    return [
        e
        for e in trug.get("edges", [])
        if e.get("from_id") == node_id or e.get("to_id") == node_id
    ]


# AGENT claude SHALL DEFINE FUNCTION get_root_node.
def get_root_node(trug: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find the FOLDER root node.

    Args:
        trug: TRUG dictionary

    Returns:
        Root node dictionary or None

    <trl>
    FUNCTION get_root_node SHALL SCAN RECORD trug THEN RETURN RECORD node SUBJECT_TO RECORD node type EQUALS DATA FOLDER OR RECORD node parent_id IS NULL.
    </trl>
    """
    for node in trug.get("nodes", []):
        if node.get("type") == "FOLDER":
            return node
    for node in trug.get("nodes", []):
        if node.get("parent_id") is None:
            return node
    return None


# AGENT claude SHALL DEFINE FUNCTION infer_node_type.
def infer_node_type(filepath: Union[str, Path]) -> str:
    """Infer TRUG node type from file extension.

    Args:
        filepath: Path to file

    Returns:
        Inferred node type string

    <trl>
    FUNCTION infer_node_type SHALL MAP DATA filepath TO DATA node_type BY FILE extension THEN RETURN DATA node_type.
    </trl>
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


# AGENT claude SHALL DEFINE FUNCTION make_node_id.
def make_node_id(name: str) -> str:
    """Generate a node ID from a filename.

    Args:
        name: Filename or identifier

    Returns:
        Sanitized node ID

    <trl>
    FUNCTION make_node_id SHALL COMPUTE DATA node_id FROM DATA name BY REPLACING DATA separator WITH DATA underscore THEN RETURN DATA node_id.
    </trl>
    """
    return name.replace(".", "_").replace("-", "_").replace(" ", "_").lower()


# AGENT claude SHALL DEFINE FUNCTION create_backup.
def create_backup(directory: Union[str, Path]) -> Optional[Path]:
    """Create a backup of folder.trug.json.

    Args:
        directory: Directory containing folder.trug.json

    Returns:
        Path to backup file, or None if no source exists

    <trl>
    FUNCTION create_backup SHALL COPY FILE folder_trug_json TO FILE backup THEN RETURN DATA backup_path SUBJECT_TO FILE folder_trug_json EXISTS.
    </trl>
    """
    source = Path(directory) / TRUG_FILENAME
    if not source.exists():
        return None
    backup_path = Path(directory) / (TRUG_FILENAME + BACKUP_SUFFIX)
    shutil.copy2(source, backup_path)
    return backup_path


# AGENT claude SHALL DEFINE FUNCTION restore_backup.
def restore_backup(directory: Union[str, Path]) -> bool:
    """Restore folder.trug.json from backup.

    Args:
        directory: Directory containing backup

    Returns:
        True if restored, False if no backup found

    <trl>
    FUNCTION restore_backup SHALL COPY FILE backup TO FILE folder_trug_json THEN RETURN DATA bool SUBJECT_TO FILE backup EXISTS.
    </trl>
    """
    dirpath = Path(directory)
    backup_path = dirpath / (TRUG_FILENAME + BACKUP_SUFFIX)
    target = dirpath / TRUG_FILENAME
    if not backup_path.exists():
        return False
    shutil.copy2(backup_path, target)
    return True
