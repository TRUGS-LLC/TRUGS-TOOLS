"""folder-init — Generate skeleton folder.trug.json from filesystem scanning.

Scans a folder's filesystem and generates a folder.trug.json with nodes
(FOLDER, DOCUMENT, SPECIFICATION, COMPONENT, TEST_SUITE, EXAMPLE_SET,
SCHEMA, TEMPLATE) and mechanical edges (contains, tests).
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

from trugs_store import InMemoryGraphStore, JsonFilePersistence

from trugs_tools.filesystem.folder_check import (
    VALID_NODE_TYPES,
    find_all_folder_trugs,
)


# Directories to skip when scanning for components
_SKIP_DIRS: Set[str] = {
    "tests", "__pycache__", ".git", "node_modules", "htmlcov",
    "EXAMPLES", "examples", ".pytest_cache", ".mypy_cache",
    ".tox", ".eggs", "dist", "build", ".coverage",
}


def _make_node_id(prefix: str, name: str) -> str:
    """Create a snake_case node ID from a prefix and name.

    Examples:
        _make_node_id("doc", "README.md") -> "doc_readme"
        _make_node_id("spec", "SPEC_folder_check.md") -> "spec_folder_check"
        _make_node_id("comp", "trugs_tools") -> "comp_trugs_tools"
    """
    stem = Path(name).stem if "." in name else name
    # Remove SPEC_ prefix and _SPEC / _SPECIFICATION suffix for spec IDs
    if prefix == "spec":
        stem = re.sub(r"^SPEC_", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"_SPEC(?:IFICATION)?$", "", stem, flags=re.IGNORECASE)
    clean = stem.lower().replace("-", "_").replace(" ", "_")
    # Remove non-alphanumeric chars except underscore
    clean = re.sub(r"[^a-z0-9_]", "", clean)
    # Collapse multiple underscores
    clean = re.sub(r"_+", "_", clean).strip("_")
    return f"{prefix}_{clean}" if clean else prefix


def _count_lines(path: Path) -> int:
    """Count non-empty lines in a file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for line in f if line.strip())
    except (OSError, UnicodeDecodeError):
        return 0


def _infer_purpose(filename: str) -> str:
    """Infer a purpose string from a filename."""
    stem = Path(filename).stem
    purposes = {
        "README": "Human quickstart and motivation",
        "AAA": "Task tracking and project status",
        "ARCHITECTURE": "System architecture documentation",
        "CONTRIBUTING": "Contribution guidelines",
        "QUICKSTART": "Quick start guide",
        "FAQ": "Frequently asked questions",
        "GLOSSARY": "Terminology and definitions",
        "VISION": "Project vision and goals",
        "RELEASE_NOTES": "Release notes and changelog",
        "CHANGELOG": "Change log",
    }
    upper = stem.upper()
    # Check for spec files (suffix or prefix)
    if upper.endswith("_SPEC") or upper.endswith("_SPECIFICATION"):
        base = re.sub(r"_SPEC(?:IFICATION)?$", "", upper)
        return f"{base.replace('_', ' ').title()} specification"
    if upper.startswith("SPEC_") or upper.startswith("SPECIFICATION_"):
        base = re.sub(r"^SPEC(?:IFICATION)?_", "", upper)
        return f"{base.replace('_', ' ').title()} specification"
    return purposes.get(upper, f"{stem.replace('_', ' ').title()} documentation")


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

def _scan_documents(folder_path: Path) -> List[dict]:
    """Scan for .md files in the folder root. Returns DOCUMENT and SPECIFICATION nodes.

    SPECIFICATION nodes are files matching *_SPEC.md or *_SPECIFICATION.md.
    All other .md files become DOCUMENT nodes.
    """
    folder_path = Path(folder_path)
    spec_pattern = re.compile(r"_SPEC\.md$|_SPECIFICATION\.md$|^SPEC_|^SPECIFICATION_", re.IGNORECASE)
    nodes: List[dict] = []

    md_files = sorted(folder_path.glob("*.md"))
    for md_file in md_files:
        name = md_file.name
        if spec_pattern.search(name):
            node_id = _make_node_id("spec", name)
            nodes.append({
                "id": node_id,
                "type": "SPECIFICATION",
                "properties": {
                    "name": name,
                    "purpose": _infer_purpose(name),
                    "format": "markdown",
                },
                "parent_id": None,  # will be set later
                "contains": [],
                "metric_level": "BASE_SPECIFICATION",
                "dimension": "folder_structure",
            })
        else:
            node_id = _make_node_id("doc", name)
            nodes.append({
                "id": node_id,
                "type": "DOCUMENT",
                "properties": {
                    "name": name,
                    "purpose": _infer_purpose(name),
                    "format": "markdown",
                },
                "parent_id": None,  # will be set later
                "contains": [],
                "metric_level": "BASE_DOCUMENT",
                "dimension": "folder_structure",
            })
    return nodes


# Subdirectory names to skip when counting files inside a component
_COMPONENT_SKIP_PARTS: Set[str] = {"tests", "__pycache__", ".pytest_cache"}


def _scan_components(folder_path: Path) -> List[dict]:
    """Scan for subdirectories containing Python code.

    Skips directories in _SKIP_DIRS. A directory qualifies as a COMPONENT
    if it contains at least one .py file.
    """
    folder_path = Path(folder_path)
    nodes: List[dict] = []

    try:
        entries = sorted(folder_path.iterdir())
    except OSError:
        return nodes

    for entry in entries:
        if not entry.is_dir():
            continue
        if entry.name in _SKIP_DIRS:
            continue
        if entry.name.startswith(".") or entry.name.startswith("ZZZ_"):
            continue

        # Check for Python files (recursive), excluding nested tests/ and __pycache__/
        py_files = [
            f for f in entry.rglob("*.py")
            if not any(part in _COMPONENT_SKIP_PARTS for part in f.relative_to(entry).parts[:-1])
        ]
        if not py_files:
            continue

        file_count = len(py_files)
        loc = sum(_count_lines(f) for f in py_files)

        node_id = _make_node_id("comp", entry.name)
        nodes.append({
            "id": node_id,
            "type": "COMPONENT",
            "properties": {
                "name": entry.name,
                "purpose": f"{entry.name.replace('_', ' ').title()} component",
                "file_count": file_count,
                "loc": loc,
            },
            "parent_id": None,
            "contains": [],
            "metric_level": "DEKA_COMPONENT",
            "dimension": "folder_structure",
        })
    return nodes


def _scan_tests(folder_path: Path, run_tests: bool = True) -> Optional[dict]:
    """Scan for tests/ directory.

    If run_tests is True, attempts to run pytest --co -q to get accurate
    test count. Falls back to counting test_*.py files.
    """
    folder_path = Path(folder_path)
    tests_dir = folder_path / "tests"
    if not tests_dir.is_dir():
        return None

    # Count test files
    test_files = sorted(
        list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("*_test.py"))
    )
    # Deduplicate (in case a file matches both patterns)
    seen = set()
    unique_test_files = []
    for f in test_files:
        if f not in seen:
            seen.add(f)
            unique_test_files.append(f)
    test_file_count = len(unique_test_files)

    test_count = test_file_count  # fallback
    test_count_source = "fallback_file_count"

    if run_tests:
        try:
            # Prefer folder-local virtualenv if it exists
            venv_python = folder_path / ".venv" / "bin" / "python"
            python_cmd = str(venv_python) if venv_python.exists() else "python"
            result = subprocess.run(
                [python_cmd, "-m", "pytest", "--co", "-q", str(tests_dir)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(folder_path),
            )
            if result.returncode != 0:
                logger.warning(
                    "pytest collection failed (exit %d) for %s — "
                    "falling back to file count",
                    result.returncode,
                    tests_dir,
                )
            else:
                # Parse output like "123 tests collected"
                match = re.search(r"(\d+)\s+tests?\s+", result.stdout)
                if match:
                    test_count = int(match.group(1))
                    test_count_source = "pytest"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning(
                "pytest not available for %s (%s) — falling back to file count",
                tests_dir,
                exc,
            )

    return {
        "id": "test_suite",
        "type": "TEST_SUITE",
        "properties": {
            "name": "tests/",
            "purpose": "Test suite",
            "test_files": test_file_count,
            "test_count": test_count,
            "test_count_source": test_count_source,
        },
        "parent_id": None,
        "contains": [],
        "metric_level": "BASE_TEST_SUITE",
        "dimension": "folder_structure",
    }


def _scan_schemas(folder_path: Path) -> Optional[dict]:
    """Scan for schemas/ directory or *.schema.json files."""
    folder_path = Path(folder_path)
    schemas_dir = folder_path / "schemas"
    schema_json_files = list(folder_path.glob("*.schema.json"))

    if schemas_dir.is_dir():
        schema_files = list(schemas_dir.iterdir())
        schema_count = len([f for f in schema_files if f.is_file()])
        return {
            "id": "schema_set",
            "type": "SCHEMA",
            "properties": {
                "name": "schemas/",
                "purpose": "Schema definitions",
                "schema_count": schema_count,
            },
            "parent_id": None,
            "contains": [],
            "metric_level": "BASE_SCHEMA",
            "dimension": "folder_structure",
        }
    elif schema_json_files:
        return {
            "id": "schema_set",
            "type": "SCHEMA",
            "properties": {
                "name": "schemas",
                "purpose": "Schema definitions",
                "schema_count": len(schema_json_files),
            },
            "parent_id": None,
            "contains": [],
            "metric_level": "BASE_SCHEMA",
            "dimension": "folder_structure",
        }
    return None


def _scan_templates(folder_path: Path) -> Optional[dict]:
    """Scan for templates/ directory."""
    folder_path = Path(folder_path)
    templates_dir = folder_path / "templates"
    if not templates_dir.is_dir():
        return None

    template_files = [f for f in templates_dir.iterdir() if f.is_file()]
    return {
        "id": "template_set",
        "type": "TEMPLATE",
        "properties": {
            "name": "templates/",
            "purpose": "Template files",
            "template_count": len(template_files),
        },
        "parent_id": None,
        "contains": [],
        "metric_level": "BASE_TEMPLATE",
        "dimension": "folder_structure",
    }


def _scan_examples(folder_path: Path) -> Optional[dict]:
    """Scan for EXAMPLES/ or examples/ directory."""
    folder_path = Path(folder_path)

    # Prefer EXAMPLES/ if both exist
    for dirname in ("EXAMPLES", "examples"):
        examples_dir = folder_path / dirname
        if examples_dir.is_dir():
            # Count files recursively
            example_count = sum(1 for f in examples_dir.rglob("*") if f.is_file())
            return {
                "id": "example_set",
                "type": "EXAMPLE_SET",
                "properties": {
                    "name": f"{dirname}/",
                    "purpose": "Example files",
                    "example_count": example_count,
                },
                "parent_id": None,
                "contains": [],
                "metric_level": "BASE_EXAMPLE_SET",
                "dimension": "folder_structure",
            }
    return None


def _read_aaa_metadata(folder_path: Path) -> dict:
    """Read phase, status, version from AAA.md.

    Only extracts metadata — NEVER uses AAA.md for file counts or structure.
    """
    folder_path = Path(folder_path)
    aaa_path = folder_path / "AAA.md"
    if not aaa_path.exists():
        return {}

    try:
        with open(aaa_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(4096)  # Only read header portion
    except OSError:
        return {}

    metadata: Dict[str, str] = {}
    patterns = {
        "phase": r"\*\*Phase:\*\*\s*(.+?)(?:\s*$|\s*\|)",
        "status": r"\*\*Status:\*\*\s*(.+?)(?:\s*$|\s*\|)",
        "version": r"\*\*Version:\*\*\s*(.+?)(?:\s*$|\s*\|)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            metadata[key] = match.group(1).strip()
    return metadata


def _read_pyproject_metadata(folder_path: Path) -> dict:
    """Read name, version, description from pyproject.toml.

    Uses simple line parsing — no tomli dependency.
    """
    folder_path = Path(folder_path)
    pyproject_path = folder_path / "pyproject.toml"
    if not pyproject_path.exists():
        return {}

    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return {}

    metadata: Dict[str, str] = {}
    # Simple line-based parsing for [project] section
    in_project = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if stripped.startswith("[") and in_project:
            break  # next section
        if in_project:
            for key in ("name", "version", "description"):
                match = re.match(rf'^{key}\s*=\s*"(.+?)"', stripped)
                if match:
                    metadata[key] = match.group(1)
    return metadata


# ---------------------------------------------------------------------------
# Edge builder
# ---------------------------------------------------------------------------

def _build_edges(
    folder_id: str,
    nodes: List[dict],
) -> List[dict]:
    """Build mechanical edges: contains + tests.

    - contains: FOLDER → every child node
    - tests: TEST_SUITE → each COMPONENT
    """
    edges: List[dict] = []

    # contains edges
    for node in nodes:
        if node["id"] == folder_id:
            continue
        edges.append({
            "from_id": folder_id,
            "to_id": node["id"],
            "relation": "contains",
            "weight": 1.0,
            "properties": {},
        })

    # tests edges: TEST_SUITE → each COMPONENT
    test_nodes = [n for n in nodes if n["type"] == "TEST_SUITE"]
    comp_nodes = [n for n in nodes if n["type"] == "COMPONENT"]
    for test_node in test_nodes:
        for comp_node in comp_nodes:
            edges.append({
                "from_id": test_node["id"],
                "to_id": comp_node["id"],
                "relation": "tests",
                "weight": 1.0,
                "properties": {},
            })

    return edges


def _build_non_contains_edges(nodes: List[dict]) -> List[dict]:
    """Build mechanical edges excluding 'contains' (handled by store.add_node).

    - tests: TEST_SUITE → each COMPONENT
    """
    edges: List[dict] = []
    test_nodes = [n for n in nodes if n.get("type") == "TEST_SUITE"]
    comp_nodes = [n for n in nodes if n.get("type") == "COMPONENT"]
    for test_node in test_nodes:
        for comp_node in comp_nodes:
            edges.append({
                "from_id": test_node["id"],
                "to_id": comp_node["id"],
                "relation": "tests",
                "weight": 1.0,
                "properties": {},
            })
    return edges


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def init_folder_trug(
    path: Union[str, Path],
    force: bool = False,
    run_tests: bool = True,
) -> dict:
    """Generate a skeleton folder.trug.json from filesystem scanning.

    Args:
        path: Path to the folder to scan.
        force: If True, allow overwriting existing folder.trug.json.
        run_tests: If True, run pytest to count tests.

    Returns:
        The generated TRUG dict.

    Raises:
        FileExistsError: If folder.trug.json exists and force is False.
        NotADirectoryError: If path is not a directory.
    """
    folder_path = Path(path).resolve()
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    trug_file = folder_path / "folder.trug.json"
    if trug_file.exists() and not force:
        raise FileExistsError(
            f"folder.trug.json already exists: {trug_file}. Use --force to overwrite."
        )

    folder_name = folder_path.name

    # Read metadata sources
    aaa_meta = _read_aaa_metadata(folder_path)
    pyproject_meta = _read_pyproject_metadata(folder_path)

    # Build FOLDER node — explicit ID, not via _make_node_id
    clean_name = re.sub(r"[^a-z0-9_]", "", folder_name.lower().replace("-", "_"))
    clean_name = re.sub(r"_+", "_", clean_name).strip("_")
    folder_id = f"{clean_name}_folder" if clean_name else "root_folder"

    folder_properties: Dict[str, Any] = {
        "name": folder_name,
        "purpose": pyproject_meta.get(
            "description",
            aaa_meta.get("status", f"{folder_name} project folder"),
        ),
    }
    if aaa_meta.get("phase"):
        folder_properties["phase"] = aaa_meta["phase"]
    if aaa_meta.get("status"):
        folder_properties["status"] = aaa_meta["status"]
    if aaa_meta.get("version"):
        folder_properties["version"] = aaa_meta["version"]
    elif pyproject_meta.get("version"):
        folder_properties["version"] = pyproject_meta["version"]

    # Run scanners
    doc_nodes = _scan_documents(folder_path)
    comp_nodes = _scan_components(folder_path)
    test_node = _scan_tests(folder_path, run_tests=run_tests)
    schema_node = _scan_schemas(folder_path)
    template_node = _scan_templates(folder_path)
    example_node = _scan_examples(folder_path)

    # Collect all child nodes
    child_nodes: List[dict] = []
    child_nodes.extend(doc_nodes)
    child_nodes.extend(comp_nodes)
    if test_node:
        child_nodes.append(test_node)
    if schema_node:
        child_nodes.append(schema_node)
    if template_node:
        child_nodes.append(template_node)
    if example_node:
        child_nodes.append(example_node)

    # Determine description and version
    description = pyproject_meta.get(
        "description",
        f"{folder_name} — auto-generated folder TRUG",
    )
    version = pyproject_meta.get("version", aaa_meta.get("version", "0.1.0"))

    # Build graph via trugs-store — enforces bidirectional invariant
    store = InMemoryGraphStore()
    store.set_metadata("name", f"{folder_name} Folder")
    store.set_metadata("version", version)
    store.set_metadata("type", "PROJECT")
    store.set_metadata("description", description)
    store.set_metadata("dimensions", {
        "folder_structure": {
            "description": f"{folder_name} components and structure",
            "base_level": "BASE",
        },
    })
    store.set_metadata("capabilities", {
        "extensions": [],
        "vocabularies": ["project_v1"],
        "profiles": [],
    })

    # Add folder node (root)
    folder_node = {
        "id": folder_id,
        "type": "FOLDER",
        "properties": folder_properties,
        "parent_id": None,
        "contains": [],
        "metric_level": "KILO_FOLDER",
        "dimension": "folder_structure",
    }
    store.add_node(folder_node)

    # Add child nodes via store — add_node(parent_id=...) enforces
    # bidirectional invariant (parent.contains, child.parent_id, CONTAINS edge)
    for node in child_nodes:
        node.setdefault("contains", [])
        store.add_node(node, parent_id=folder_id)

    # Add mechanical edges (tests relations)
    all_nodes = [folder_node] + child_nodes
    test_edges = _build_non_contains_edges(all_nodes)
    for edge in test_edges:
        store.add_edge(edge)

    # Return as dict (CLI writes the file)
    result: Dict[str, Any] = dict(store.get_metadata())
    result["nodes"] = store.find_nodes()
    result["edges"] = store.get_edges()
    return result


def find_folders_without_trug(root: Union[str, Path]) -> List[Path]:
    """Find folders that could benefit from a folder.trug.json but don't have one.

    Scans for directories containing at least one significant file
    (*.md, *.py, pyproject.toml) that don't already have folder.trug.json.
    Excludes hidden directories, zzz_ prefixed, and common ignore dirs.
    """
    root = Path(root).resolve()
    results: List[Path] = []
    skip_names = {
        "__pycache__", "node_modules", "htmlcov", ".pytest_cache",
        ".mypy_cache", ".tox", ".eggs", "dist", "build",
        "tests", "schemas", "templates",
    }

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith("ZZZ_")
            and not d.startswith(".")
            and d not in skip_names
        ]
        dp = Path(dirpath)
        if (dp / "folder.trug.json").exists():
            continue
        # Check if folder has significant content
        has_content = any(
            f.endswith(".md") or f.endswith(".py") or f == "pyproject.toml"
            for f in filenames
        )
        if has_content:
            results.append(dp)

    return sorted(results)
