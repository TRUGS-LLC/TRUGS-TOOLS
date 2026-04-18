"""folder-map — Build root-level graph from all folder.trug.json files.

Discovers all folder.trug.json files under a root directory, loads each
TRUG's FOLDER node, resolves cross-folder edges, and assembles a unified
root graph.

Design rules:
  1. Never modify individual folder TRUGs (read-only).
  2. Resolve cross-folder edges (alias:node_id) by verifying targets exist.
  3. Deterministic output — same input produces byte-identical JSON.
  4. Zero runtime dependencies beyond stdlib.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from trugs_tools.filesystem.folder_check import find_all_folder_trugs


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FolderInfo:
    """Information about a single folder TRUG."""

    path: Path
    alias: str
    trug: dict
    folder_node: Optional[dict]
    node_ids: Set[str]


@dataclass
class MapResult:
    """Result of a folder-map operation."""

    folder_count: int = 0
    resolved_edges: List[dict] = field(default_factory=list)
    unresolved_edges: List[dict] = field(default_factory=list)
    orphaned_folders: List[str] = field(default_factory=list)
    root_graph: Optional[dict] = None
    changes: List[str] = field(default_factory=list)

    @property
    def edge_count(self) -> int:
        return len(self.resolved_edges)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _folder_alias(folder_name: str) -> str:
    """Convert folder directory name to its lowercase alias.

    Examples:
        TRUGS_TOOLS → trugs_tools
        CODE_FACTORY → code_factory
        packages → packages
    """
    return folder_name.lower()


def _find_folder_node(trug: dict) -> Optional[dict]:
    """Find the FOLDER-type node in a TRUG."""
    for node in trug.get("nodes", []):
        if node.get("type") == "FOLDER":
            return node
    return None


def _load_folder_trugs(
    trug_paths: List[Path],
    root: Path,
) -> Dict[str, FolderInfo]:
    """Load all folder TRUGs and build an index by alias.

    Args:
        trug_paths: Paths to folder.trug.json files.
        root: Root directory (its own TRUG is excluded from the index).

    Returns:
        Dict mapping alias → FolderInfo.
    """
    folders: Dict[str, FolderInfo] = {}
    root_resolved = root.resolve()

    for trug_path in trug_paths:
        folder_dir = trug_path.parent.resolve()

        # Exclude the root directory's own TRUG
        if folder_dir == root_resolved:
            continue

        folder_name = folder_dir.name
        alias = _folder_alias(folder_name)

        with open(trug_path, "r", encoding="utf-8") as f:
            trug = json.load(f)

        folder_node = _find_folder_node(trug)
        node_ids = {n["id"] for n in trug.get("nodes", []) if "id" in n}

        folders[alias] = FolderInfo(
            path=trug_path,
            alias=alias,
            trug=trug,
            folder_node=folder_node,
            node_ids=node_ids,
        )

    return folders


def _is_cross_folder_ref(ref: str) -> bool:
    """Check if a node reference is a cross-folder reference (contains ':')."""
    return ":" in ref


def _parse_cross_folder_ref(ref: str) -> Tuple[str, str]:
    """Parse a cross-folder reference into (alias, node_id).

    The alias is lowercased for case-insensitive matching.

    Example: 'TRUGS_PROTOCOL:spec_validation' → ('trugs_protocol', 'spec_validation')
    """
    parts = ref.split(":", 1)
    return parts[0].lower(), parts[1]


def _resolve_cross_folder_edges(
    folders: Dict[str, FolderInfo],
) -> Tuple[List[dict], List[dict]]:
    """Resolve all cross-folder edges across all TRUGs.

    Returns:
        Tuple of (resolved_edges, unresolved_edges).
        Each resolved edge is a dict with from_folder, to_folder, relation, weight.
    """
    resolved: List[dict] = []
    unresolved: List[dict] = []

    for alias, info in folders.items():
        for edge in info.trug.get("edges", []):
            from_id = edge.get("from_id", "")
            to_id = edge.get("to_id", "")
            relation = edge.get("relation", "")
            weight = edge.get("weight", 1.0)

            is_from_cross = _is_cross_folder_ref(from_id)
            is_to_cross = _is_cross_folder_ref(to_id)

            if not is_from_cross and not is_to_cross:
                continue  # Internal edge, skip

            # Determine source folder
            if is_from_cross:
                from_alias, from_node = _parse_cross_folder_ref(from_id)
            else:
                from_alias = alias
                from_node = from_id

            # Determine target folder
            if is_to_cross:
                to_alias, to_node = _parse_cross_folder_ref(to_id)
            else:
                to_alias = alias
                to_node = to_id

            edge_info = {
                "source_folder": from_alias,
                "target_folder": to_alias,
                "from_id": from_id,
                "to_id": to_id,
                "from_node": from_node,
                "to_node": to_node,
                "relation": relation,
                "weight": weight,
                "origin_trug": alias,
            }

            # Validate source
            source_ok = True
            if is_from_cross:
                if from_alias not in folders:
                    source_ok = False
                elif from_node not in folders[from_alias].node_ids:
                    source_ok = False

            # Validate target
            target_ok = True
            if is_to_cross:
                if to_alias not in folders:
                    target_ok = False
                elif to_node not in folders[to_alias].node_ids:
                    target_ok = False

            if source_ok and target_ok:
                resolved.append(edge_info)
            else:
                reasons = []
                if not source_ok:
                    reasons.append(f"source {from_id} not found")
                if not target_ok:
                    reasons.append(f"target {to_id} not found")
                edge_info["reason"] = "; ".join(reasons)
                unresolved.append(edge_info)

    return resolved, unresolved


def _make_folder_node_id(alias: str) -> str:
    """Generate root-graph node ID for a folder."""
    return f"folder_{alias}"


def _make_folder_node(alias: str, info: FolderInfo) -> dict:
    """Create a COMPONENT node for the root graph from a folder's FOLDER node."""
    node_id = _make_folder_node_id(alias)
    props: Dict[str, Any] = {
        "name": info.path.parent.name,
    }

    # Pull properties from the FOLDER node if available
    if info.folder_node:
        folder_props = info.folder_node.get("properties", {})
        if "purpose" in folder_props:
            props["purpose"] = folder_props["purpose"]
        if "phase" in folder_props:
            props["phase"] = folder_props["phase"]
        if "status" in folder_props:
            props["status"] = folder_props["status"]
        if "version" in folder_props:
            props["version"] = folder_props["version"]
    else:
        props["purpose"] = f"{info.path.parent.name} subfolder"

    return {
        "id": node_id,
        "type": "COMPONENT",
        "properties": props,
        "parent_id": "root_folder",
        "contains": [],
        "metric_level": "DEKA_COMPONENT",
        "dimension": "folder_structure",
    }


def _find_orphaned_folders(
    folders: Dict[str, FolderInfo],
    resolved_edges: List[dict],
) -> List[str]:
    """Find folders with no cross-folder edges."""
    connected: Set[str] = set()
    for edge in resolved_edges:
        connected.add(edge["source_folder"])
        connected.add(edge["target_folder"])

    orphaned = sorted(
        alias for alias in folders if alias not in connected
    )
    return orphaned


def _build_root_graph(
    folders: Dict[str, FolderInfo],
    resolved_edges: List[dict],
    root_name: str = "TRUGS-DEVELOPMENT",
) -> dict:
    """Assemble the root-level TRUG graph.

    Args:
        folders: Index of folder aliases → FolderInfo.
        resolved_edges: List of resolved cross-folder edge dicts.
        root_name: Name for the root graph.

    Returns:
        Root TRUG dict.
    """
    # Root FOLDER node
    folder_aliases = sorted(folders.keys())
    folder_node_ids = [_make_folder_node_id(a) for a in folder_aliases]

    root_node = {
        "id": "root_folder",
        "type": "FOLDER",
        "properties": {
            "name": root_name,
            "purpose": f"Monorepo root — {len(folders)} active subfolders",
            "verified": False,
            "stale": False,
            "last_verified": None,
        },
        "parent_id": None,
        "contains": folder_node_ids,
        "metric_level": "KILO_FOLDER",
        "dimension": "folder_structure",
    }

    # Folder COMPONENT nodes
    folder_nodes = []
    for alias in folder_aliases:
        folder_nodes.append(_make_folder_node(alias, folders[alias]))

    # All nodes sorted by id
    all_nodes = [root_node] + sorted(folder_nodes, key=lambda n: n["id"])

    # Contains edges
    contains_edges = []
    for node_id in folder_node_ids:
        contains_edges.append({
            "from_id": "root_folder",
            "to_id": node_id,
            "relation": "contains",
            "weight": 1.0,
        })

    # Cross-folder edges (deduplicated and mapped to root-level node IDs)
    seen: Set[Tuple[str, str, str]] = set()
    cross_edges: List[dict] = []
    for edge in resolved_edges:
        from_node_id = _make_folder_node_id(edge["source_folder"])
        to_node_id = _make_folder_node_id(edge["target_folder"])
        relation = edge["relation"]
        key = (from_node_id, to_node_id, relation)
        if key not in seen:
            seen.add(key)
            cross_edges.append({
                "from_id": from_node_id,
                "to_id": to_node_id,
                "relation": relation,
                "weight": edge.get("weight", 1.0),
            })

    # All edges sorted by (relation, from_id, to_id) for determinism
    all_edges = sorted(
        contains_edges + cross_edges,
        key=lambda e: (e["relation"], e["from_id"], e["to_id"]),
    )

    return {
        "name": f"{root_name} Root",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": f"Root-level TRUG for the {root_name} monorepo — connects {len(folders)} active subfolders",
        "dimensions": {
            "folder_structure": {
                "description": f"Top-level monorepo structure — {len(folders)} active subdirectories",
                "base_level": "BASE",
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["project_v1"],
            "profiles": [],
        },
        "nodes": all_nodes,
        "edges": all_edges,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def map_folder_trugs(
    root: Union[str, Path],
    dry_run: bool = False,
    output: Optional[Union[str, Path]] = None,
) -> MapResult:
    """Build root-level graph from all folder.trug.json files.

    Args:
        root: Root directory to scan for folder.trug.json files.
        dry_run: If True, do not write to disk.
        output: Custom output path. Defaults to root/folder.trug.json.

    Returns:
        MapResult describing the operation.

    Raises:
        NotADirectoryError: If root is not a directory.
        FileNotFoundError: If no folder.trug.json files found.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")

    # Step 1: Find all folder TRUGs
    trug_paths = find_all_folder_trugs(root_path)
    if not trug_paths:
        raise FileNotFoundError(
            f"No folder.trug.json files found under {root_path}"
        )

    # Step 2: Load and index all TRUGs
    folders = _load_folder_trugs(trug_paths, root_path)
    if not folders:
        raise FileNotFoundError(
            f"No subfolder folder.trug.json files found under {root_path}"
        )

    result = MapResult()
    result.folder_count = len(folders)

    # Step 3: Resolve cross-folder edges
    resolved, unresolved = _resolve_cross_folder_edges(folders)
    result.resolved_edges = resolved
    result.unresolved_edges = unresolved

    # Step 4: Detect orphaned folders
    orphaned = _find_orphaned_folders(folders, resolved)
    result.orphaned_folders = orphaned

    # Step 5: Build root graph
    root_name = root_path.name
    root_graph = _build_root_graph(folders, resolved, root_name)
    result.root_graph = root_graph

    # Step 6: Build change descriptions
    result.changes.append(
        f"Mapped {result.folder_count} folder TRUGs → root graph"
    )
    result.changes.append(
        f"Resolved: {len(resolved)} cross-folder edges"
    )
    if unresolved:
        result.changes.append(
            f"Unresolved: {len(unresolved)} edges"
        )
        for e in unresolved:
            result.changes.append(
                f"  ⚠ {e['origin_trug']}: {e['from_id']} → {e['to_id']} ({e.get('reason', 'unknown')})"
            )
    if orphaned:
        result.changes.append(
            f"Orphaned: {len(orphaned)} folders ({', '.join(orphaned)})"
        )
    node_count = len(root_graph["nodes"])
    edge_count = len(root_graph["edges"])
    result.changes.append(
        f"Root graph: {node_count} nodes, {edge_count} edges"
    )

    # Step 7: Write output
    if not dry_run:
        output_path = Path(output) if output else root_path / "folder.trug.json"
        json_str = json.dumps(root_graph, indent=2, ensure_ascii=False) + "\n"
        output_path.write_text(json_str, encoding="utf-8")
        result.changes.append(f"Wrote: {output_path}")

    return result
