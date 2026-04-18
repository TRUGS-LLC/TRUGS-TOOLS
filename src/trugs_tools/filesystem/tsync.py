"""tsync - Discover files and infer edges for a TRUG graph.

Scans a directory to find new files not yet in the graph, adds them,
and attempts to infer edges from import statements and file references.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from trugs_tools.filesystem.utils import (
    TRUG_FILENAME,
    get_node_by_id,
    get_root_node,
    infer_node_type,
    load_graph,
    make_node_id,
    save_graph,
)


# Files and directories to ignore during sync
IGNORE_PATTERNS: Set[str] = {
    TRUG_FILENAME,
    TRUG_FILENAME + ".backup",
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".mypy_cache",
    "htmlcov",
    ".coverage",
    ".tox",
    ".eggs",
    "*.egg-info",
    "dist",
    "build",
}


def tsync(
    directory: Union[str, Path],
    dry_run: bool = False,
    infer_edges: bool = True,
) -> Dict[str, Any]:
    """Synchronize folder.trug.json with actual directory contents.

    Discovers new files and optionally infers edges from file references.

    Args:
        directory: Directory containing folder.trug.json
        dry_run: If True, return changes without modifying graph
        infer_edges: If True, attempt to infer edges from file contents

    Returns:
        Dict with 'added_nodes', 'removed_nodes', 'inferred_edges', and 'trug'

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist
    """
    dirpath = Path(directory).resolve()
    trug = load_graph(dirpath)

    root = get_root_node(trug)
    if root is None:
        raise ValueError("No root node found in TRUG")

    # Build set of existing node names
    existing_names: Set[str] = set()
    for node in trug.get("nodes", []):
        name = node.get("properties", {}).get("name", "")
        if name:
            existing_names.add(name)

    # Discover new files
    added_nodes: List[Dict[str, Any]] = []
    for item in sorted(dirpath.iterdir()):
        if _should_ignore(item.name):
            continue
        if item.name not in existing_names:
            node_id = make_node_id(item.name)
            # Skip if ID already exists (collision)
            if get_node_by_id(trug, node_id) is not None:
                continue

            ntype = "FOLDER" if item.is_dir() else infer_node_type(item)
            metric = "KILO_FOLDER" if ntype == "FOLDER" else f"BASE_{ntype}"

            node: Dict[str, Any] = {
                "id": node_id,
                "type": ntype,
                "properties": {
                    "name": item.name,
                    "purpose": f"{'Directory' if item.is_dir() else 'File'}: {item.name}",
                },
                "parent_id": root["id"],
                "contains": [],
                "metric_level": metric,
                "dimension": "folder_structure",
            }
            added_nodes.append(node)

    # Find nodes whose files no longer exist
    removed_nodes: List[str] = []
    for node in trug.get("nodes", []):
        if node.get("type") == "FOLDER" and node.get("parent_id") is None:
            continue  # Don't remove root
        name = node.get("properties", {}).get("name", "")
        if name and not (dirpath / name).exists():
            removed_nodes.append(node["id"])

    # Infer edges from file contents
    inferred_edges: List[Dict[str, Any]] = []
    if infer_edges:
        inferred_edges = _infer_edges(dirpath, trug, added_nodes)

    if not dry_run:
        # Add new nodes
        for node in added_nodes:
            trug["nodes"].append(node)
            if "contains" not in root:
                root["contains"] = []
            root["contains"].append(node["id"])

        # Add inferred edges
        existing_edges = {
            (e.get("from_id"), e.get("to_id"), e.get("relation"))
            for e in trug.get("edges", [])
        }
        for edge in inferred_edges:
            key = (edge["from_id"], edge["to_id"], edge["relation"])
            if key not in existing_edges:
                trug["edges"].append(edge)

        save_graph(dirpath, trug)

    return {
        "added_nodes": [n["id"] for n in added_nodes],
        "removed_nodes": removed_nodes,
        "inferred_edges": inferred_edges,
        "trug": trug,
    }


def _should_ignore(name: str) -> bool:
    """Check if a file/directory should be ignored."""
    if name.startswith("."):
        return True
    if name in IGNORE_PATTERNS:
        return True
    for pattern in IGNORE_PATTERNS:
        if "*" in pattern and name.endswith(pattern.replace("*", "")):
            return True
    return False


def _infer_edges(
    dirpath: Path,
    trug: Dict[str, Any],
    new_nodes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Infer edges from file contents (imports, references).

    Currently supports:
      - Python imports (from X import Y, import X)
      - Markdown links ([text](file.md))
      - JSON references to other files
    """
    all_nodes = trug.get("nodes", []) + new_nodes
    node_name_map: Dict[str, str] = {}
    for node in all_nodes:
        name = node.get("properties", {}).get("name", "")
        if name:
            node_name_map[name] = node["id"]
            # Also map without extension
            stem = Path(name).stem
            if stem not in node_name_map:
                node_name_map[stem] = node["id"]

    edges: List[Dict[str, Any]] = []

    for node in all_nodes:
        name = node.get("properties", {}).get("name", "")
        if not name:
            continue
        filepath = dirpath / name
        if not filepath.is_file():
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        refs = _extract_references(name, content)
        for ref_name in refs:
            if ref_name in node_name_map:
                target_id = node_name_map[ref_name]
                if target_id != node["id"]:
                    # Design decision (2026-02-20): Inferred edges get NO weight.
                    # Weight = curator endorsement. These are machine-discovered structural
                    # facts, not opinions. Owner can add weight later via tlink --weight.
                    edges.append({
                        "from_id": node["id"],
                        "to_id": target_id,
                        "relation": "REFERENCES",
                    })

    return edges


def _extract_references(filename: str, content: str) -> Set[str]:
    """Extract file references from content based on file type."""
    refs: Set[str] = set()

    if filename.endswith(".py"):
        # Python: from X import Y, import X
        for match in re.finditer(r"^(?:from|import)\s+([\w.]+)", content, re.MULTILINE):
            module = match.group(1).split(".")[0]
            refs.add(module)
            refs.add(module + ".py")

    elif filename.endswith(".md"):
        # Markdown: [text](file)
        for match in re.finditer(r"\[.*?\]\(([^)]+)\)", content):
            target = match.group(1)
            if not target.startswith(("http://", "https://", "#")):
                refs.add(target)
                refs.add(Path(target).name)

    return refs
