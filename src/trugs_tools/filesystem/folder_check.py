"""folder-check - Validate folder.trug.json files for correctness and staleness.

Checks structural integrity, node/edge validity, cross-folder edge syntax,
filesystem existence, and contains-array consistency against the governance
specification defined in TRUGS_FILES/SPEC_folder_governance.md.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from trugs_store import InMemoryGraphStore, JsonFilePersistence


# -- Governance constants (from TRUGS_FILES/SPEC_folder_governance.md) --------

VALID_NODE_TYPES: Dict[str, str] = {
    "FOLDER": "KILO_FOLDER",
    "DOCUMENT": "BASE_DOCUMENT",
    "PROSE": "BASE_DOCUMENT",
    "SPECIFICATION": "BASE_SPECIFICATION",
    "COMPONENT": "DEKA_COMPONENT",
    "TEST_SUITE": "BASE_TEST_SUITE",
    "EXAMPLE_SET": "BASE_EXAMPLE_SET",
    "SCHEMA": "BASE_SCHEMA",
    "TEMPLATE": "BASE_TEMPLATE",
}

VALID_INTERNAL_RELATIONS: Set[str] = {
    "contains", "uses", "produces", "validates",
    "implements", "tests", "describes", "governs",
}

VALID_CROSS_FOLDER_RELATIONS: Set[str] = {
    "uses", "implements", "has_reference_impl",
    "validates", "produces",
}

REQUIRED_TOP_LEVEL_KEYS: Set[str] = {
    "name", "version", "type", "dimensions", "capabilities", "nodes", "edges",
}

# Files/dirs ignored when checking for on-disk items not in TRUG
IGNORE_ON_DISK: Set[str] = {
    "folder.trug.json",
    "folder.trug.json.backup",
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".mypy_cache",
    "htmlcov",
    ".coverage",
    ".tox",
    ".eggs",
    "dist",
    "build",
    ".DS_Store",
    "prose",  # PROSE zone files are indexed as PROSE nodes, not directory nodes
}


# -- Result dataclass ---------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD checkresult AS RECORD class.
class CheckResult:
    """Result of checking a single folder.trug.json file."""

    __slots__ = ("path", "errors", "warnings", "node_count", "edge_count")

    def __init__(self, path: str) -> None:
        self.path: str = path
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.node_count: int = 0
        self.edge_count: int = 0

    # AGENT claude SHALL DEFINE FUNCTION ok.
    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    # AGENT claude SHALL DEFINE FUNCTION to_dict.
    def to_dict(self) -> Dict[str, Any]:
        return {
            "folder": self.path,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "stats": {
                "nodes": self.node_count,
                "edges": self.edge_count,
            },
        }


# -- Core checking logic ------------------------------------------------------

# AGENT claude SHALL DEFINE FUNCTION check_folder_trug.
def check_folder_trug(
    trug_path: Union[str, Path],
    check_filesystem: bool = True,
) -> CheckResult:
    """Validate a single folder.trug.json file.

    Args:
        trug_path: Path to a folder.trug.json file.
        check_filesystem: Whether to verify files exist on disk.

    Returns:
        CheckResult with errors and warnings.
    """
    trug_path = Path(trug_path).resolve()
    result = CheckResult(str(trug_path))

    # -- 1. Valid JSON — load via trugs-store ---------------------------------
    try:
        persistence = JsonFilePersistence()
        store = persistence.load(str(trug_path))
    except json.JSONDecodeError as exc:
        result.errors.append(f"Invalid JSON: {exc}")
        return result
    except FileNotFoundError:
        result.errors.append(f"File not found: {trug_path}")
        return result

    # -- 2. Required top-level keys -------------------------------------------
    # Also check raw JSON for top-level keys (store absorbs them as metadata)
    try:
        with open(trug_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception:
        raw_data = {}

    if not isinstance(raw_data, dict):
        result.errors.append("Top-level value must be a JSON object")
        return result

    missing_keys = REQUIRED_TOP_LEVEL_KEYS - set(raw_data.keys())
    for key in sorted(missing_keys):
        result.errors.append(f"Missing required top-level key: '{key}'")
    if missing_keys:
        return result  # can't continue without structure

    nodes: List[Dict[str, Any]] = store.find_nodes()
    edges: List[Dict[str, Any]] = store.get_edges()
    result.node_count = store.node_count()
    result.edge_count = store.edge_count()

    # Build lookup maps via store
    node_ids: Set[str] = {n["id"] for n in nodes}
    node_by_id: Dict[str, Dict[str, Any]] = {n["id"]: n for n in nodes}
    folder_nodes: List[Dict[str, Any]] = store.find_nodes(type="FOLDER")

    # -- 3. Exactly 1 FOLDER node (parent_id=null) ----------------------------
    root_folder_nodes = [n for n in folder_nodes if n.get("parent_id") is None]
    if len(root_folder_nodes) == 0:
        result.errors.append("No FOLDER node with parent_id=null found")
    elif len(root_folder_nodes) > 1:
        ids = [n.get("id", "?") for n in root_folder_nodes]
        result.errors.append(
            f"Multiple FOLDER nodes with parent_id=null: {', '.join(ids)}"
        )

    folder_node = root_folder_nodes[0] if root_folder_nodes else None

    # -- 4. Valid node types ---------------------------------------------------
    for node in nodes:
        ntype = node.get("type", "")
        nid = node.get("id", "?")
        if ntype not in VALID_NODE_TYPES:
            result.errors.append(
                f"Node '{nid}': invalid type '{ntype}' "
                f"(valid: {', '.join(sorted(VALID_NODE_TYPES))})"
            )

    # -- 5. Correct metric_levels ----------------------------------------------
    for node in nodes:
        ntype = node.get("type", "")
        nid = node.get("id", "?")
        mlevel = node.get("metric_level", "")
        expected = VALID_NODE_TYPES.get(ntype)
        if expected and mlevel != expected:
            result.errors.append(
                f"Node '{nid}': metric_level '{mlevel}' should be "
                f"'{expected}' for type '{ntype}'"
            )

    # -- 6 & 7. Valid edge relations -------------------------------------------
    for edge in edges:
        relation = edge.get("relation", "")
        from_id = edge.get("from_id", "")
        to_id = edge.get("to_id", "")
        is_cross_folder = ":" in str(to_id)

        if is_cross_folder:
            # -- 7. Cross-folder edge relations
            if relation not in VALID_CROSS_FOLDER_RELATIONS:
                result.errors.append(
                    f"Edge '{from_id}' -> '{to_id}': invalid cross-folder "
                    f"relation '{relation}' "
                    f"(valid: {', '.join(sorted(VALID_CROSS_FOLDER_RELATIONS))})"
                )
            # -- 8. Cross-folder edge syntax
            parts = str(to_id).split(":")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                result.errors.append(
                    f"Edge '{from_id}' -> '{to_id}': cross-folder to_id must "
                    f"have format 'folder_name:node_id'"
                )
        else:
            # -- 6. Internal edge relations
            if relation not in VALID_INTERNAL_RELATIONS:
                result.errors.append(
                    f"Edge '{from_id}' -> '{to_id}': invalid internal "
                    f"relation '{relation}' "
                    f"(valid: {', '.join(sorted(VALID_INTERNAL_RELATIONS))})"
                )

    # -- 9. Contains-array consistency ----------------------------------------
    if folder_node is not None:
        contains_list = folder_node.get("contains", [])
        contains_edges_to: Set[str] = set()
        folder_id = folder_node.get("id", "")
        for edge in edges:
            if (
                edge.get("from_id") == folder_id
                and edge.get("relation") == "contains"
            ):
                contains_edges_to.add(edge.get("to_id", ""))

        for child_id in contains_list:
            if child_id not in contains_edges_to:
                result.errors.append(
                    f"Contains-array lists '{child_id}' but no 'contains' "
                    f"edge from '{folder_id}' to '{child_id}' exists"
                )

    # -- 10. No dangling edge references (internal) ---------------------------
    for edge in edges:
        from_id = edge.get("from_id", "")
        to_id = edge.get("to_id", "")
        if from_id not in node_ids:
            result.errors.append(
                f"Edge from_id '{from_id}' does not reference any node"
            )
        if ":" not in str(to_id) and to_id not in node_ids:
            result.errors.append(
                f"Edge to_id '{to_id}' does not reference any node"
            )

    # -- 11. Filesystem existence for DOCUMENT/SPECIFICATION nodes ------------
    folder_dir = trug_path.parent
    if check_filesystem:
        for node in nodes:
            ntype = node.get("type", "")
            nid = node.get("id", "?")
            if ntype in ("DOCUMENT", "SPECIFICATION"):
                props = node.get("properties", {})
                # Skip existence check for planned (not yet created) files
                if props.get("planned"):
                    continue
                # Skip existence check for stale nodes — stale flag already
                # acknowledges the file is absent; the W-stale warning covers it
                if props.get("stale"):
                    continue
                node_name = props.get("name", "")
                if node_name:
                    file_path = folder_dir / node_name
                    if not file_path.exists():
                        result.errors.append(
                            f"Node '{nid}' references file '{node_name}' "
                            f"but it does not exist in {folder_dir}"
                        )

    # -- Warnings --------------------------------------------------------------

    # W1. On-disk items not in TRUG
    if check_filesystem:
        node_names: Set[str] = set()
        for node in nodes:
            name = node.get("properties", {}).get("name", "")
            if name:
                node_names.add(name)
        try:
            for item in sorted(folder_dir.iterdir()):
                if item.name in IGNORE_ON_DISK:
                    continue
                if item.name.startswith("."):
                    continue
                if item.name.startswith("ZZZ_"):
                    continue
                # Check for egg-info directories
                if item.name.endswith(".egg-info"):
                    continue
                if item.name not in node_names:
                    result.warnings.append(
                        f"On-disk item '{item.name}' is not represented "
                        f"by any node"
                    )
        except PermissionError:
            pass

    # W2. Stale flags
    for node in nodes:
        nid = node.get("id", "?")
        props = node.get("properties", {})
        if props.get("stale") is True:
            result.warnings.append(f"Node '{nid}' has stale=true")

    # W3. Empty contains
    if folder_node is not None:
        contains_list = folder_node.get("contains", [])
        if len(contains_list) == 0:
            result.warnings.append(
                f"FOLDER node '{folder_node.get('id', '?')}' has empty "
                f"contains array"
            )

    return result


# -- Multi-file scanning -------------------------------------------------------

# AGENT claude SHALL DEFINE FUNCTION find_all_folder_trugs.
def find_all_folder_trugs(root: Union[str, Path]) -> List[Path]:
    """Find all folder.trug.json files under root, excluding ZZZ_ dirs.

    Args:
        root: Root directory to search.

    Returns:
        Sorted list of Path objects.
    """
    root = Path(root).resolve()
    results: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ZZZ_ and hidden directories
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith("ZZZ_") and not d.startswith(".")
        ]
        if "folder.trug.json" in filenames:
            results.append(Path(dirpath) / "folder.trug.json")
    return sorted(results)


# AGENT claude SHALL DEFINE FUNCTION check_all.
def check_all(
    paths: Optional[List[Union[str, Path]]] = None,
    scan_all: bool = False,
    root: Optional[Union[str, Path]] = None,
    check_filesystem: bool = True,
) -> List[CheckResult]:
    """Check multiple folder.trug.json files.

    Args:
        paths: Explicit paths to check (files or directories).
        scan_all: If True, find all folder.trug.json under root.
        root: Root for --all scanning (default: cwd).
        check_filesystem: Whether to verify files exist on disk.

    Returns:
        List of CheckResult.
    """
    trug_paths: List[Path] = []

    if scan_all:
        search_root = Path(root) if root else Path.cwd()
        trug_paths = find_all_folder_trugs(search_root)
    elif paths:
        for p in paths:
            p = Path(p).resolve()
            if p.is_dir():
                candidate = p / "folder.trug.json"
                if candidate.exists():
                    trug_paths.append(candidate)
                else:
                    r = CheckResult(str(p))
                    r.errors.append(
                        f"No folder.trug.json found in directory: {p}"
                    )
                    trug_paths.append(p)  # will fail in check
            else:
                trug_paths.append(p)

    results: List[CheckResult] = []
    for tp in trug_paths:
        results.append(check_folder_trug(tp, check_filesystem=check_filesystem))

    return results


# -- Output formatting ---------------------------------------------------------

# AGENT claude SHALL DEFINE FUNCTION format_text.
def format_text(results: List[CheckResult], quiet: bool = False) -> str:
    """Format results as human-readable text.

    Args:
        results: List of CheckResult.
        quiet: If True, only summary line.

    Returns:
        Formatted string.
    """
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    if quiet:
        return (
            f"{total_errors} error(s), {total_warnings} warning(s) "
            f"across {len(results)} file(s)"
        )

    lines: List[str] = []
    for r in results:
        lines.append(f"\n{r.path}:")
        lines.append(f"  Nodes: {r.node_count}  Edges: {r.edge_count}")
        if r.errors:
            for e in r.errors:
                lines.append(f"  ❌ {e}")
        if r.warnings:
            for w in r.warnings:
                lines.append(f"  ⚠️  {w}")
        if r.ok and not r.warnings:
            lines.append("  ✅ All checks passed")

    lines.append("")
    lines.append(f"{total_errors} error(s), {total_warnings} warning(s) "
                 f"across {len(results)} file(s)")
    return "\n".join(lines)


# AGENT claude SHALL DEFINE FUNCTION format_json.
def format_json(results: List[CheckResult]) -> str:
    """Format results as JSON.

    Args:
        results: List of CheckResult.

    Returns:
        JSON string.
    """
    output = [r.to_dict() for r in results]
    return json.dumps(output, indent=2, ensure_ascii=False)
