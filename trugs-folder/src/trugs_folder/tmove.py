# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""tmove - File move with graph update and attempted rollback.

Moves a file when present and updates its node in folder.trug.json.
Reparenting updates parent_id and contains[]; edges are unchanged.
On failure, attempts to restore the graph backup and undo the rename.
Rollback is not atomic and cannot recover overwritten destination contents.

<trl>
PROCESS tmove SHALL MOVE FILE node AND SHALL UPDATE RECORD graph THEN RESTORE FILE node SUBJECT_TO failure.
</trl>
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from trugs_folder.utils import (
    create_backup,
    get_node_by_id,
    load_graph,
    restore_backup,
    save_graph,
)


# AGENT claude SHALL DEFINE FUNCTION _collect_descendants.
def _collect_descendants(trug: Dict[str, Any], node_id: str) -> Set[str]:
    """Collect every descendant of a node, following contains[] and parent_id.

    Both directions of the hierarchy are followed because the two can be out
    of step in a graph under repair, and either one alone would miss a
    descendant the other records.

    The walk is bounded by a seen-set: the graph may ALREADY contain a cycle
    (that is the state this check exists to stop tmove from creating), and an
    unbounded walk over one would never return.

    Args:
        trug: TRUG dictionary
        node_id: ID of the node whose descendants are wanted

    Returns:
        Set of descendant node IDs (never includes node_id itself)

    <trl>
    FUNCTION _collect_descendants SHALL RETURN DATA descendant_ids.
    </trl>
    """
    nodes = trug.get("nodes", [])
    children_by_parent: Dict[str, List[str]] = {}
    for node in nodes:
        nid = node.get("id")
        pid = node.get("parent_id")
        if isinstance(nid, str) and isinstance(pid, str):
            children_by_parent.setdefault(pid, []).append(nid)

    contains_by_id: Dict[str, List[str]] = {}
    for node in nodes:
        nid = node.get("id")
        contains = node.get("contains")
        if isinstance(nid, str) and isinstance(contains, list):
            contains_by_id[nid] = [c for c in contains if isinstance(c, str)]

    descendants: Set[str] = set()
    stack: List[str] = [node_id]
    seen: Set[str] = {node_id}
    while stack:
        current = stack.pop()
        for child in children_by_parent.get(current, []) + contains_by_id.get(
            current, []
        ):
            if child in seen:
                continue
            seen.add(child)
            descendants.add(child)
            stack.append(child)
    return descendants


# AGENT claude SHALL DEFINE FUNCTION tmove.
def tmove(
    directory: Union[str, Path],
    node_id: str,
    new_name: Optional[str] = None,
    new_parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Move/rename a node in the TRUG graph with attempted rollback.

    Renames the physical file when it exists and updates the graph even if it
    does not. On failure, attempts to restore the graph backup and undo the
    rename. Rollback is not atomic and cannot recover overwritten destination
    contents.

    Args:
        directory: Directory containing folder.trug.json
        node_id: ID of the node to move/rename
        new_name: New filename (rename)
        new_parent_id: New parent node ID (reparent)

    Returns:
        Updated TRUG dictionary

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
        ValueError: If node or new parent not found, or if the new parent is
            the node itself or one of its descendants (that would build a
            parent_id cycle)

    <trl>
    FUNCTION tmove SHALL MOVE FILE node AND SHALL UPDATE RECORD graph AND SHALL_NOT MOVE RECORD node TO RECORD descendant THEN RETURN RECORD trug SUBJECT_TO atomic_rollback ON failure.
    </trl>
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

            # A node may not become its own parent, nor a child of anything
            # already beneath it: either closes the parent_id chain into a
            # ring the validator rejects as HIERARCHY_CYCLE. Raised the same
            # way as the not-found check above so the rollback path below
            # undoes any rename already applied.
            if new_parent_id == node_id:
                raise ValueError(f"New parent is the node itself: {new_parent_id}")
            if new_parent_id in _collect_descendants(trug, node_id):
                raise ValueError(
                    f"New parent is a descendant of {node_id}: {new_parent_id}"
                )

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
