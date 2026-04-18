"""folder-sync — Update existing folder.trug.json with current filesystem facts.

Re-scans a folder using the same scanners as folder-init, then patches
factual properties (counts, LOC, phase) on existing nodes while preserving
all human-curated edges and properties.

Hard Rules:
  1. Never touch edges (except adding contains/tests for NEW nodes).
  2. Never remove nodes (mark stale instead).
  3. Preserve human-curated properties (purpose, verified, custom).
  4. Only update factual/scannable properties.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

from trugs_tools.filesystem.folder_init import (
    _scan_documents,
    _scan_components,
    _scan_tests,
    _scan_schemas,
    _scan_templates,
    _scan_examples,
    _read_aaa_metadata,
    _read_pyproject_metadata,
)


# Properties that folder-sync is allowed to update (factual/scannable).
_UPDATABLE_PROPERTIES: Dict[str, Set[str]] = {
    "COMPONENT": {"file_count", "loc"},
    "TEST_SUITE": {"test_count", "test_files", "test_count_source"},
    "SCHEMA": {"schema_count"},
    "TEMPLATE": {"template_count"},
    "EXAMPLE_SET": {"example_count"},
}


@dataclass
class SyncResult:
    """Result of a folder-sync operation."""

    updated_nodes: List[str] = field(default_factory=list)
    new_nodes: List[str] = field(default_factory=list)
    stale_nodes: List[str] = field(default_factory=list)
    cleared_stale: List[str] = field(default_factory=list)
    pruned_nodes: List[str] = field(default_factory=list)
    edges_added: int = 0
    edges_total: int = 0
    changes: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.updated_nodes
            or self.new_nodes
            or self.stale_nodes
            or self.cleared_stale
            or self.pruned_nodes
            or self.edges_added > 0
        )


def sync_folder_trug(
    path: Union[str, Path],
    run_tests: bool = True,
    dry_run: bool = False,
    prune_after: int = 7,
) -> SyncResult:
    """Sync a folder.trug.json with the current filesystem state.

    Args:
        path: Path to the folder containing folder.trug.json.
        run_tests: If True, run pytest to count tests.
        dry_run: If True, do not write changes to disk.
        prune_after: Remove nodes stale for this many consecutive syncs.
                     0 disables pruning.

    Returns:
        SyncResult describing what changed.

    Raises:
        FileNotFoundError: If folder.trug.json does not exist.
        NotADirectoryError: If path is not a directory.
    """
    folder_path = Path(path).resolve()
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    trug_file = folder_path / "folder.trug.json"
    if not trug_file.exists():
        raise FileNotFoundError(
            f"No folder.trug.json found: {trug_file}. Use folder-init first."
        )

    # Step 1: Load existing TRUG
    with open(trug_file, "r", encoding="utf-8") as f:
        existing = json.load(f)

    # Step 2: Re-scan filesystem using folder-init scanners
    fresh_nodes = _scan_all(folder_path, run_tests=run_tests)
    fresh_by_id = {n["id"]: n for n in fresh_nodes}

    # Build index of existing nodes
    existing_nodes = existing.get("nodes", [])
    existing_by_id = {n["id"]: n for n in existing_nodes}

    result = SyncResult()
    result.edges_total = len(existing.get("edges", []))

    # Step 3: Match existing nodes to fresh nodes and update
    for node in existing_nodes:
        node_id = node["id"]
        node_type = node.get("type", "")

        if node_id in fresh_by_id:
            fresh = fresh_by_id[node_id]

            # Clear stale flag if it was previously stale
            props = node.get("properties", {})
            if props.get("stale"):
                del props["stale"]
                if "stale_reason" in props:
                    del props["stale_reason"]
                result.cleared_stale.append(node_id)
                result.changes.append(
                    f"Cleared stale: {node_id} (file returned)"
                )
            # Clear stale tracking fields when node is not stale
            _clear_stale_tracking(props)

            # Update factual properties only
            changes = _update_factual_properties(node, fresh, node_type)
            if changes:
                result.updated_nodes.append(node_id)
                result.changes.extend(changes)
        else:
            # Node not found in fresh scan — check if it should be marked stale
            if node_type == "FOLDER":
                # FOLDER node is special — never mark stale
                continue

            # Before marking stale, check if the node has a file/name
            # property that resolves to an existing file on disk.
            # The scanner only creates per-directory component nodes, but
            # hand-curated TRUGs may have per-file component nodes with
            # a "file" property (e.g., "src/trugs2go/errors.py") or
            # DOCUMENT/SPECIFICATION nodes whose "name" is a filename.
            props = node.get("properties", {})
            if _node_file_exists(folder_path, props, node_type):
                # File exists on disk — clear stale if it was previously set
                if props.get("stale"):
                    del props["stale"]
                    if "stale_reason" in props:
                        del props["stale_reason"]
                    result.cleared_stale.append(node_id)
                    result.changes.append(
                        f"Cleared stale: {node_id} (file verified on disk)"
                    )
                _clear_stale_tracking(props)
                continue

            if not props.get("stale"):
                props["stale"] = True
                props["stale_reason"] = "file not found on disk"
                props["stale_since"] = datetime.now(timezone.utc).isoformat()
                props["stale_count"] = 1
                node["properties"] = props
                result.stale_nodes.append(node_id)
                result.changes.append(
                    f"Stale: {node_id} (file not found)"
                )
            else:
                # Already stale — increment stale_count
                props["stale_count"] = props.get("stale_count", 0) + 1
                if "stale_since" not in props:
                    props["stale_since"] = datetime.now(timezone.utc).isoformat()
                node["properties"] = props
                result.stale_nodes.append(node_id)
                result.changes.append(
                    f"Stale: {node_id} (stale_count={props['stale_count']})"
                )

    # Step 4: Detect new nodes not in existing TRUG
    folder_node = _find_folder_node(existing_nodes)
    folder_id = folder_node["id"] if folder_node else None

    new_edges: List[dict] = []
    for fresh_id, fresh_node in fresh_by_id.items():
        if fresh_id not in existing_by_id:
            # New node detected — add it
            if folder_id:
                fresh_node["parent_id"] = folder_id
            existing_nodes.append(fresh_node)
            result.new_nodes.append(fresh_id)
            result.changes.append(
                f"New node: {fresh_id} ({fresh_node.get('type', 'UNKNOWN')})"
            )

            # Add contains edge from FOLDER to new node
            if folder_id:
                new_edges.append({
                    "from_id": folder_id,
                    "to_id": fresh_id,
                    "relation": "contains",
                    "weight": 1.0,
                    "properties": {},
                })

                # Update FOLDER's contains array
                if folder_node is not None:
                    contains = folder_node.get("contains", [])
                    if fresh_id not in contains:
                        contains.append(fresh_id)
                        folder_node["contains"] = contains

            # If new node is TEST_SUITE, add tests edges to all COMPONENTs
            if fresh_node.get("type") == "TEST_SUITE":
                for n in existing_nodes:
                    if n.get("type") == "COMPONENT" and n["id"] != fresh_id:
                        new_edges.append({
                            "from_id": fresh_id,
                            "to_id": n["id"],
                            "relation": "tests",
                            "weight": 1.0,
                            "properties": {},
                        })

            # If new node is COMPONENT, add tests edges from all TEST_SUITEs
            if fresh_node.get("type") == "COMPONENT":
                for n in existing_nodes:
                    if n.get("type") == "TEST_SUITE" and n["id"] != fresh_id:
                        new_edges.append({
                            "from_id": n["id"],
                            "to_id": fresh_id,
                            "relation": "tests",
                            "weight": 1.0,
                            "properties": {},
                        })

    # Add new edges
    if new_edges:
        edges = existing.get("edges", [])
        edges.extend(new_edges)
        existing["edges"] = edges
        result.edges_added = len(new_edges)
        result.edges_total = len(edges)

    # Step 4b: Ghost node pruning
    if prune_after > 0:
        pruned_ids: List[str] = []
        for node in list(existing_nodes):
            props = node.get("properties", {})
            if (
                props.get("stale")
                and props.get("stale_count", 0) >= prune_after
            ):
                pruned_ids.append(node["id"])
        # Remove pruned nodes (preserve order, deterministic)
        if pruned_ids:
            pruned_set = set(pruned_ids)
            existing_nodes[:] = [
                n for n in existing_nodes if n["id"] not in pruned_set
            ]
            # Remove edges referencing pruned nodes
            edges = existing.get("edges", [])
            edges[:] = [
                e for e in edges
                if e.get("from_id") not in pruned_set
                and e.get("to_id") not in pruned_set
            ]
            # Remove from FOLDER contains
            if folder_node is not None:
                contains = folder_node.get("contains", [])
                folder_node["contains"] = [
                    c for c in contains if c not in pruned_set
                ]
            result.pruned_nodes.extend(pruned_ids)
            for pid in pruned_ids:
                result.changes.append(f"Pruned: {pid} (stale >= {prune_after} syncs)")

    # Step 4c: Component status auto-advance (Fix 2)
    for node in existing_nodes:
        props = node.get("properties", {})
        status = props.get("status")
        if status == "NOT_STARTED":
            node_type = node.get("type", "")
            # Check if file exists and has code
            loc = props.get("loc", 0)
            file_exists = (
                node["id"] in fresh_by_id
                or _node_file_exists(folder_path, props, node_type)
            )
            if file_exists and loc > 0:
                props["status"] = "PRESENT"
                node["properties"] = props
                if node["id"] not in result.updated_nodes:
                    result.updated_nodes.append(node["id"])
                result.changes.append(
                    f"Auto-advanced: {node['id']} (NOT_STARTED → PRESENT)"
                )

    # Read pyproject metadata once (used in steps 5 and 6)
    pyproject_meta = _read_pyproject_metadata(folder_path)

    # Step 5: Update FOLDER node metadata
    if folder_node is not None:
        aaa_meta = _read_aaa_metadata(folder_path)
        folder_changes = _update_folder_metadata(
            folder_node, aaa_meta, pyproject_meta
        )
        if folder_changes:
            if folder_node["id"] not in result.updated_nodes:
                result.updated_nodes.append(folder_node["id"])
            result.changes.extend(folder_changes)

    # Step 6: Update top-level TRUG metadata
    top_changes = _update_top_level_metadata(existing, pyproject_meta)
    if top_changes:
        result.changes.extend(top_changes)

    # Step 6b: Prose/factual divergence warning
    _warn_prose_factual_divergence(existing_nodes)

    # Step 7: Write if not dry-run
    existing["nodes"] = existing_nodes
    if not dry_run and result.has_changes:
        from trugs_store.persistence.dual_write import write_trug
        write_trug(existing, trug_file)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _node_file_exists(folder_path: Path, props: dict, node_type: str) -> bool:
    """Check if a node's referenced file exists on disk.

    For COMPONENT/DOCUMENT/SPECIFICATION nodes, checks the 'file' property
    first, then falls back to the 'name' property. Paths are resolved
    relative to the folder containing folder.trug.json.

    Returns True if a matching file is found on disk, False otherwise.
    """
    # Try the explicit "file" property first (e.g., "src/trugs2go/errors.py")
    file_path = props.get("file")
    if file_path:
        candidate = folder_path / file_path
        if candidate.exists():
            return True

    # For DOCUMENT/SPECIFICATION nodes, try "name" as a filename
    if node_type in ("DOCUMENT", "SPECIFICATION"):
        name = props.get("name", "")
        if name and not "/" in name:
            candidate = folder_path / name
            if candidate.exists():
                return True

    # Try "ref" property for SPECIFICATION nodes (e.g., "SPECIFICATIONS.md § S-01")
    if node_type == "SPECIFICATION":
        ref = props.get("ref", "")
        if ref:
            # Extract filename before any section marker
            ref_file = ref.split("§")[0].split("#")[0].strip()
            if ref_file:
                candidate = folder_path / ref_file
                if candidate.exists():
                    return True

    return False

def _scan_all(folder_path: Path, run_tests: bool = True) -> List[dict]:
    """Run all folder-init scanners and return a flat list of fresh nodes."""
    nodes: List[dict] = []
    nodes.extend(_scan_documents(folder_path))
    nodes.extend(_scan_components(folder_path))
    test_node = _scan_tests(folder_path, run_tests=run_tests)
    if test_node:
        nodes.append(test_node)
    schema_node = _scan_schemas(folder_path)
    if schema_node:
        nodes.append(schema_node)
    template_node = _scan_templates(folder_path)
    if template_node:
        nodes.append(template_node)
    example_node = _scan_examples(folder_path)
    if example_node:
        nodes.append(example_node)
    return nodes


def _find_folder_node(nodes: List[dict]) -> Optional[dict]:
    """Find the FOLDER node in a list of nodes."""
    for node in nodes:
        if node.get("type") == "FOLDER":
            return node
    return None


def _update_factual_properties(
    existing_node: dict,
    fresh_node: dict,
    node_type: str,
) -> List[str]:
    """Update only factual/scannable properties on an existing node.

    Returns list of human-readable change descriptions.
    """
    updatable = _UPDATABLE_PROPERTIES.get(node_type, set())
    if not updatable:
        return []

    existing_props = existing_node.get("properties", {})
    fresh_props = fresh_node.get("properties", {})
    changes: List[str] = []

    for key in updatable:
        if key in fresh_props:
            old_val = existing_props.get(key)
            new_val = fresh_props[key]
            if old_val != new_val:
                existing_props[key] = new_val
                changes.append(
                    f"Updated: {existing_node['id']} ({key}: {old_val}→{new_val})"
                )

    existing_node["properties"] = existing_props
    return changes


def _update_folder_metadata(
    folder_node: dict,
    aaa_meta: dict,
    pyproject_meta: dict,
) -> List[str]:
    """Update factual metadata on the FOLDER node from AAA.md / pyproject.toml."""
    props = folder_node.get("properties", {})
    changes: List[str] = []
    node_id = folder_node["id"]

    for key in ("phase", "status"):
        if key in aaa_meta:
            old_val = props.get(key)
            new_val = aaa_meta[key]
            if old_val != new_val:
                props[key] = new_val
                changes.append(f"Updated: {node_id} ({key}: {old_val}→{new_val})")

    # Version: prefer AAA.md, fall back to pyproject.toml
    new_version = aaa_meta.get("version") or pyproject_meta.get("version")
    if new_version:
        old_version = props.get("version")
        if old_version != new_version:
            props["version"] = new_version
            changes.append(
                f"Updated: {node_id} (version: {old_version}→{new_version})"
            )

    folder_node["properties"] = props
    return changes


def _update_top_level_metadata(
    trug: dict,
    pyproject_meta: dict,
) -> List[str]:
    """Update top-level TRUG fields from pyproject.toml."""
    changes: List[str] = []

    if "version" in pyproject_meta:
        old = trug.get("version")
        new = pyproject_meta["version"]
        if old != new:
            trug["version"] = new
            changes.append(f"Updated: top-level version ({old}→{new})")

    if "description" in pyproject_meta:
        old = trug.get("description")
        new = pyproject_meta["description"]
        if old != new:
            trug["description"] = new
            changes.append(f"Updated: top-level description")

    return changes


def _clear_stale_tracking(props: dict) -> None:
    """Remove stale_since and stale_count from properties when node is not stale."""
    props.pop("stale_since", None)
    props.pop("stale_count", None)


# Factual property names that hold integer values on nodes
_FACTUAL_INT_PROPS = {"loc", "file_count", "test_count", "test_files"}


def _warn_prose_factual_divergence(nodes: List[dict]) -> None:
    """Emit warnings when string properties contain integers that contradict factual values.

    Scans all string properties on each node for integer tokens, then
    compares against factual integer properties on the same node.
    Does NOT modify any prose — warning only.
    """
    integer_re = re.compile(r"\b\d+\b")

    for node in nodes:
        props = node.get("properties", {})
        node_id = node.get("id", "unknown")

        # Collect factual integer values present on this node
        factual: Dict[str, int] = {}
        for key in _FACTUAL_INT_PROPS:
            if key in props and isinstance(props[key], int):
                factual[key] = props[key]

        if not factual:
            continue

        # Dedupe: track (field_name, token) pairs already warned
        warned: Set[tuple] = set()

        for field_name, value in props.items():
            if not isinstance(value, str):
                continue
            tokens = integer_re.findall(value)
            for token in tokens:
                token_int = int(token)
                # Compare against each factual property
                for fact_name, fact_val in factual.items():
                    if token_int != fact_val and (field_name, token) not in warned:
                        warned.add((field_name, token))
                        logger.warning(
                            "Prose/factual divergence on node %s: "
                            "field '%s' contains token '%s' but %s=%d",
                            node_id,
                            field_name,
                            token,
                            fact_name,
                            fact_val,
                        )
