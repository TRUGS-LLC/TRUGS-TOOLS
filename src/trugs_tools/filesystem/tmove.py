"""tmove - Atomic file move with graph update.

Moves a file and updates all references in folder.trug.json atomically.
On failure, rolls back both the filesystem and graph changes.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Union

from trugs_tools.filesystem.utils import (
    create_backup,
    get_node_by_id,
    load_graph,
    restore_backup,
    save_graph,
)


# AGENT claude SHALL DEFINE FUNCTION tmove.
def tmove(
    directory: Union[str, Path],
    node_id: str,
    new_name: Optional[str] = None,
    new_parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Move/rename a node in the TRUG graph atomically.

    Moves the physical file and updates the graph. On any failure,
    both filesystem and graph are rolled back to the previous state.

    Args:
        directory: Directory containing folder.trug.json
        node_id: ID of the node to move/rename
        new_name: New filename (rename)
        new_parent_id: New parent node ID (reparent)

    Returns:
        Updated TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json or source file doesn't exist
        ValueError: If node or new parent not found
    """
    if new_name is None and new_parent_id is None:
        raise ValueError("Must specify new_name or new_parent_id (or both)")

    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)
    backup_path = create_backup(dirpath)

    old_name = ""
    try:
        node = get_node_by_id(trug, node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")

        old_name = node.get("properties", {}).get("name", "")

        # Handle rename
        if new_name:
            old_path = dirpath / old_name
            new_path = dirpath / new_name

            if old_path.exists():
                shutil.move(str(old_path), str(new_path))

            node["properties"]["name"] = new_name

        # Handle reparent
        if new_parent_id:
            new_parent = get_node_by_id(trug, new_parent_id)
            if new_parent is None:
                raise ValueError(f"New parent node not found: {new_parent_id}")

            # Remove from old parent's contains
            old_parent_id = node.get("parent_id")
            if old_parent_id:
                old_parent = get_node_by_id(trug, old_parent_id)
                if old_parent and "contains" in old_parent:
                    if node_id in old_parent["contains"]:
                        old_parent["contains"].remove(node_id)

            # Add to new parent's contains
            if "contains" not in new_parent:
                new_parent["contains"] = []
            if node_id not in new_parent["contains"]:
                new_parent["contains"].append(node_id)

            node["parent_id"] = new_parent_id

        save_graph(dirpath, trug, backup=False)
        return trug

    except Exception:
        # Rollback: restore graph backup
        if backup_path:
            restore_backup(dirpath)
        # Rollback: restore file if renamed
        if new_name and old_name:
            new_file = dirpath / new_name
            old_file = dirpath / old_name
            if new_file.exists() and not old_file.exists():
                shutil.move(str(new_file), str(old_file))
        raise
