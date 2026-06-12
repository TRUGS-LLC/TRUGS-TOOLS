# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""trug-a-folder — the TRUGS cartography CLI (trugs_folder, T2).

AAA #2373 commons cleave: the cartography command handlers, re-homed onto their
owning package. This module imports only T1 (trugs_tools) + T2 (trugs_folder) +
trugs_store — NEVER any T3 system module (trugs_start), so the published
trugs-folder wheel carries zero AGPL system code (invariant: folder_cli
SHALL_NOT LOAD ANY system_tier).

Entry point: ``trug-a-folder <verb> [args...]``.
"""
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

from trugs_tools import __version__, __codename__
from trugs_tools.validator import validate_trug
from trugs_tools.generator import generate_trug, SUPPORTED_BRANCHES
from trugs_folder.renderer import render_all, render_architecture
from trugs_folder.folder_check import (
    find_all_folder_trugs as _find_all_folder_trugs,
)
from trugs_folder.tinit import tinit
from trugs_folder.tadd import tadd
from trugs_folder.tls import tls
from trugs_folder.tcd import tcd
from trugs_folder.tfind import tfind
from trugs_folder.tmove import tmove
from trugs_folder.tlink import tlink, tunlink, VALID_RELATIONS
from trugs_folder.tget import tget
from trugs_folder.tupdate import tupdate
from trugs_folder.tdelete import tdelete
from trugs_folder.tunlink import tunlink as tunlink_standalone
from trugs_folder.tdim import tdim
from trugs_folder.twatch import twatch
from trugs_folder.tsync import tsync
from trugs_folder.twhere import twhere
from trugs_folder.folder_check import (
    check_all,
    format_json,
    format_text,
)
from trugs_folder.folder_init import (
    init_folder_trug,
    find_folders_without_trug,
)
from trugs_folder.folder_sync import sync_folder_trug
from trugs_folder.folder_map import map_folder_trugs
from trugs_store.persistence.dual_write import write_trug


# Per-verb help epilogs (A5, STANDARD_cli_help.md): copy-pasteable examples +
# documented exit codes. Additive prose only — the flag contract is frozen (I4).
_EPILOGS = {
    "info": """\
examples:
  trug-a-folder info folder.trug.json
  trug-a-folder info graph.trug.json -f json

exit codes:
  0  success
  1  file not found / invalid JSON / error
  2  usage error (bad flags or arguments)""",
    "init": """\
examples:
  trug-a-folder init myproject --scan -d "My first mapped folder"
  trug-a-folder init . --force -n "My Project"

exit codes:
  0  success
  1  folder.trug.json already exists (without --force) / error
  2  usage error (bad flags or arguments)""",
    "add": """\
examples:
  trug-a-folder add main.py docs/notes.md
  trug-a-folder add config.json -t DOCUMENT --purpose "App config"

exit codes:
  0  success
  1  duplicate node / missing graph / error
  2  usage error (bad flags or arguments)""",
    "ls": """\
examples:
  trug-a-folder ls
  trug-a-folder ls --edges -f json

exit codes:
  0  success
  1  no folder.trug.json found / error
  2  usage error (bad flags or arguments)""",
    "find": """\
examples:
  trug-a-folder find -t COMPONENT
  trug-a-folder find -n '\\.py$' -f json

exit codes:
  0  success (including zero matches)
  1  no folder.trug.json found / error
  2  usage error (bad flags or arguments)""",
    "where": """\
examples:
  trug-a-folder where renderer
  trug-a-folder where 'folder_.*' -f json

exit codes:
  0  success (including zero matches)
  1  error
  2  usage error (bad flags or arguments)""",
    "mv": """\
examples:
  trug-a-folder mv main_py --name app.py
  trug-a-folder mv notes_md --parent docs

exit codes:
  0  success
  1  node not found / error
  2  usage error (bad flags or arguments)""",
    "link": """\
examples:
  trug-a-folder link main_py utils_py -r uses
  trug-a-folder link main_py utils_py -r uses --remove

exit codes:
  0  success
  1  invalid relation / node not found / error
  2  usage error (bad flags or arguments)""",
    "dim": """\
examples:
  trug-a-folder dim list
  trug-a-folder dim add -n security -d "Security view"
  trug-a-folder dim set --node main_py -n security

exit codes:
  0  success
  1  missing required option for the action / error
  2  usage error (bad flags or arguments)""",
    "check": """\
examples:
  trug-a-folder check myproject
  trug-a-folder check --all --strict

exit codes:
  0  all checks passed
  1  errors found (or warnings, with --strict)
  2  runtime error / no folder.trug.json files found""",
    "render": """\
examples:
  trug-a-folder render architecture myproject
  trug-a-folder render architecture --all --root .

exit codes:
  0  success
  1  folder.trug.json not found / render error
  2  write error""",
    "sync": """\
examples:
  trug-a-folder sync myproject
  trug-a-folder sync --all --no-tests

exit codes:
  0  success
  1  no folder.trug.json / not a directory
  2  runtime error (or partial failure with --all)""",
    "export": """\
examples:
  trug-a-folder export myproject
  trug-a-folder export --all --root .

exit codes:
  0  success
  1  graph not in database / error
  2  usage error (bad flags or arguments)""",
    "import": """\
examples:
  trug-a-folder import myproject
  trug-a-folder import --all --root .

exit codes:
  0  success
  1  import error
  2  usage error (bad flags or arguments)""",
}


# AGENT claude SHALL DEFINE FUNCTION validate_command.


# ---------------------------------------------------------------------------
# Cartography command handlers (extracted from the monolithic dispatcher,
# AAA #2373 SP2 — owned by trugs_folder, the cartography tier).
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE FUNCTION info_command.
def info_command(args: Optional[list] = None) -> int:
    """Show information about TRUG files.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION info_command SHALL READ FILE trug THEN EMIT DATA info.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder info", description="Show information about TRUG files",
        epilog=_EPILOGS["info"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", help="TRUG file to analyze")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    parsed_args = parser.parse_args(args)

    try:
        from trugs_tools.validator import load_trug

        trug = load_trug(parsed_args.file)

        # Extract information
        info = {
            "name": trug.get("name", "Unknown"),
            "version": trug.get("version", "Unknown"),
            "type": trug.get("type", "Unknown"),
            "branch": trug.get("branch", "Unknown"),
            "node_count": len(trug.get("nodes", [])),
            "edge_count": len(trug.get("edges", [])),
            "extensions": trug.get("extensions", []),
        }

        # Count node types
        node_types: dict[str, int] = {}
        for node in trug.get("nodes", []):
            node_type = node.get("type", "Unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        info["node_types"] = node_types

        # Count edge relations
        edge_relations: dict[str, int] = {}
        for edge in trug.get("edges", []):
            relation = edge.get("relation", "Unknown")
            edge_relations[relation] = edge_relations.get(relation, 0) + 1
        info["edge_relations"] = edge_relations

        # Output
        if parsed_args.format == "text":
            print(f"\nTRUG Information: {parsed_args.file}")
            print("=" * 60)
            print(f"Name:       {info['name']}")
            print(f"Version:    {info['version']}")
            print(f"Type:       {info['type']}")
            print(f"Branch:     {info['branch']}")
            print(f"Nodes:      {info['node_count']}")
            print(f"Edges:      {info['edge_count']}")

            if info["extensions"]:
                print(f"Extensions: {', '.join(info['extensions'])}")

            if info["node_types"]:
                print("\nNode Types:")
                for node_type, count in sorted(info["node_types"].items()):
                    print(f"  {node_type}: {count}")

            if info["edge_relations"]:
                print("\nEdge Relations:")
                for relation, count in sorted(info["edge_relations"].items()):
                    print(f"  {relation}: {count}")

            print("=" * 60)
        else:
            print(json.dumps(info, indent=2))

        return 0

    except FileNotFoundError:
        print(f"Error: File not found: {parsed_args.file}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tinit_command.
def tinit_command(args: Optional[list] = None) -> int:
    """Initialize folder.trug.json in a directory.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tinit_command SHALL WRITE FILE folder_trug SUBJECT_TO directory EXISTS.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder init", description="Initialize folder.trug.json in a directory",
        epilog=_EPILOGS["init"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Target directory (default: current directory)",
    )
    parser.add_argument("-n", "--name", help="Project name (default: directory name)")
    parser.add_argument("-d", "--description", default="", help="Project description")
    parser.add_argument(
        "--scan", action="store_true", help="Scan directory for existing files"
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing folder.trug.json"
    )
    parser.add_argument(
        "-q",
        "--qualifying-interest",
        default=None,
        help="Hub qualifying interest (what this TRUG curates)",
    )

    parsed = parser.parse_args(args)

    try:
        result = tinit(
            directory=parsed.directory,
            name=parsed.name,
            description=parsed.description,
            scan=parsed.scan,
            force=parsed.force,
            qualifying_interest=parsed.qualifying_interest,
        )
        node_count = len(result.get("nodes", []))
        print(f"Initialized folder.trug.json ({node_count} node(s))")
        return 0
    except FileExistsError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tadd_command.
def tadd_command(args: Optional[list] = None) -> int:
    """Add files to a TRUG graph.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tadd_command SHALL APPEND RECORD node TO FILE folder_trug.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder add", description="Add files to the TRUG graph",
        epilog=_EPILOGS["add"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="+", help="Files to add")
    parser.add_argument(
        "-C",
        "--directory",
        default=".",
        help="Directory containing folder.trug.json (default: .)",
    )
    parser.add_argument(
        "-t", "--type", dest="node_type", help="Override inferred node type"
    )
    parser.add_argument("-p", "--parent", dest="parent_id", help="Parent node ID")
    parser.add_argument(
        "--purpose", default="", help="Purpose description for added nodes"
    )

    parsed = parser.parse_args(args)

    try:
        tadd(
            directory=parsed.directory,
            files=parsed.files,
            node_type=parsed.node_type,
            parent_id=parsed.parent_id,
            purpose=parsed.purpose,
        )
        print(f"Added {len(parsed.files)} file(s) to graph")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tls_command.
def tls_command(args: Optional[list] = None) -> int:
    """List directory contents with graph enrichment.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tls_command SHALL READ FILE folder_trug THEN EMIT DATA listing.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder ls", description="List directory contents with TRUG metadata",
        epilog=_EPILOGS["ls"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "directory", nargs="?", default=".", help="Directory to list (default: .)"
    )
    parser.add_argument("--node", dest="node_id", help="List children of specific node")
    parser.add_argument("--edges", action="store_true", help="Show edge details")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    parsed = parser.parse_args(args)

    try:
        result = tls(
            directory=parsed.directory,
            node_id=parsed.node_id,
            show_edges=parsed.edges,
            format=parsed.format,
        )
        if parsed.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tcd_command.
def tcd_command(args: Optional[list] = None) -> int:
    """Navigate to a node in the TRUG graph.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tcd_command SHALL RESOLVE RECORD node THEN EMIT DATA node_view.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs tcd", description="Navigate the TRUG graph"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="/",
        help="Target node ID, '..' for parent, '/' for root",
    )
    parser.add_argument(
        "-C", "--directory", default=".", help="Directory containing folder.trug.json"
    )
    parser.add_argument(
        "--current", help="Current node ID (needed for '..' navigation)"
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    parsed = parser.parse_args(args)

    try:
        result = tcd(
            directory=parsed.directory,
            target=parsed.target,
            current=parsed.current,
        )

        if parsed.format == "json":
            print(json.dumps(result, indent=2, default=str))
        else:
            node = result["node"]
            name = node.get("properties", {}).get("name", node["id"])
            print(f"Node: {name} (id={node['id']}, type={node.get('type', '?')})")
            print(f"Path: {result['path']}")
            if result["children"]:
                print(f"Children ({len(result['children'])}):")
                for c in result["children"]:
                    print(f"  [{c['type']:14s}] {c['name']} (id={c['id']})")
            if result["edges"]:
                print(f"Edges ({len(result['edges'])}):")
                for e in result["edges"]:
                    print(f"  {e['from_id']} --[{e['relation']}]--> {e['to_id']}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tfind_command.
def tfind_command(args: Optional[list] = None) -> int:
    """Query nodes in a TRUG graph.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tfind_command SHALL FILTER RECORD node THEN RETURN DATA result.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder find", description="Query nodes in a TRUG graph",
        epilog=_EPILOGS["find"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-C", "--directory", default=".", help="Directory containing folder.trug.json"
    )
    parser.add_argument("-t", "--type", dest="node_type", help="Filter by node type")
    parser.add_argument(
        "-n", "--name", dest="name_pattern", help="Filter by name (regex pattern)"
    )
    parser.add_argument("-d", "--dimension", help="Filter by dimension")
    parser.add_argument("-e", "--edge-relation", help="Filter by edge relation")
    parser.add_argument("-m", "--metric-level", help="Filter by metric level")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    parsed = parser.parse_args(args)

    try:
        result = tfind(
            directory=parsed.directory,
            node_type=parsed.node_type,
            name_pattern=parsed.name_pattern,
            dimension=parsed.dimension,
            edge_relation=parsed.edge_relation,
            metric_level=parsed.metric_level,
            format=parsed.format,
        )
        if parsed.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION twhere_command.
def twhere_command(args: Optional[list] = None) -> int:
    """Search across all folder.trug.json files for a concept.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION twhere_command SHALL SCAN FILE folder_trug THEN RETURN DATA matches.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder where",
        description="Search across all folder.trug.json files for a concept, node, or file",
        epilog=_EPILOGS["where"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", help="Search term (regex supported)")
    parser.add_argument(
        "-C",
        "--directory",
        default=".",
        help="Root directory to search from (default: current)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    parsed = parser.parse_args(args)

    try:
        results = twhere(
            query=parsed.query,
            root=parsed.directory,
        )
        if not results:
            print(f"No matches for '{parsed.query}'")
            return 0
        if parsed.format == "json":
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                path_info = f" → {r['file_path']}" if r["file_path"] else ""
                print(f"  {r['folder']}/{r['node_id']} [{r['node_type']}]{path_info}")
                print(f"    {r['match_field']}: {r['match_value']}")
            print(f"\n{len(results)} match(es)")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tmove_command.
def tmove_command(args: Optional[list] = None) -> int:
    """Move/rename a node in the TRUG graph.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tmove_command SHALL MAP RECORD node TO DATA new_location THEN WRITE FILE folder_trug.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder mv", description="Move/rename a node in the TRUG graph",
        epilog=_EPILOGS["mv"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("node_id", help="Node ID to move/rename")
    parser.add_argument(
        "-C", "--directory", default=".", help="Directory containing folder.trug.json"
    )
    parser.add_argument("--name", dest="new_name", help="New filename")
    parser.add_argument("--parent", dest="new_parent_id", help="New parent node ID")

    parsed = parser.parse_args(args)

    try:
        tmove(
            directory=parsed.directory,
            node_id=parsed.node_id,
            new_name=parsed.new_name,
            new_parent_id=parsed.new_parent_id,
        )
        print(f"Moved node: {parsed.node_id}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tlink_command.
def tlink_command(args: Optional[list] = None) -> int:
    """Create or remove typed edges between nodes.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tlink_command SHALL WRITE RECORD edge TO FILE folder_trug SUBJECT_TO relation VALID.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder link", description="Create or remove typed edges between nodes",
        epilog=_EPILOGS["link"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("from_id", help="Source node ID")
    parser.add_argument("to_id", help="Target node ID")
    parser.add_argument(
        "-r",
        "--relation",
        required=True,
        help=f"Edge relation type ({', '.join(sorted(VALID_RELATIONS))})",
    )
    parser.add_argument(
        "-C", "--directory", default=".", help="Directory containing folder.trug.json"
    )
    parser.add_argument(
        "--remove", action="store_true", help="Remove the edge instead of creating it"
    )
    parser.add_argument(
        "-w",
        "--weight",
        type=float,
        default=None,
        help="Edge weight (0.0-1.0): curator endorsement strength",
    )

    parsed = parser.parse_args(args)

    try:
        if parsed.remove:
            tunlink(
                directory=parsed.directory,
                from_id=parsed.from_id,
                to_id=parsed.to_id,
                relation=parsed.relation,
            )
            print(
                f"Removed edge: {parsed.from_id} --[{parsed.relation}]--> {parsed.to_id}"
            )
        else:
            tlink(
                directory=parsed.directory,
                from_id=parsed.from_id,
                to_id=parsed.to_id,
                relation=parsed.relation,
                weight=parsed.weight,
            )
            if parsed.weight is not None:
                print(
                    f"Created edge: {parsed.from_id} --[{parsed.relation}, {parsed.weight}]--> {parsed.to_id}"
                )
            else:
                print(
                    f"Created edge: {parsed.from_id} --[{parsed.relation}]--> {parsed.to_id}"
                )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tget_command.
def tget_command(args: Optional[list] = None) -> int:
    """Read full content of a specific node.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tget_command SHALL READ RECORD node THEN EMIT DATA node_content.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tget",
        description="Read full content of a specific node in a TRUG graph",
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("node_id", help="ID of node to read")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--edges", action="store_true", help="Also show connected edges"
    )

    parsed = parser.parse_args(args)

    try:
        # Resolve directory from trug file path
        trug_path = Path(parsed.trug_file).resolve()
        directory = trug_path.parent

        result = tget(
            directory=directory,
            node_id=parsed.node_id,
            show_edges=parsed.edges,
            format=parsed.format,
        )
        if parsed.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tupdate_command.
def tupdate_command(args: Optional[list] = None) -> int:
    """Update properties on an existing node.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tupdate_command SHALL UPDATE RECORD node THEN WRITE FILE folder_trug.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tupdate",
        description="Update properties on an existing node in a TRUG graph",
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("node_id", help="ID of node to update")
    parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        help="Set property: key=value (repeatable)",
    )
    parser.add_argument("--type", dest="node_type", help="Change node type")
    parser.add_argument("--parent", dest="parent_id", help="Change parent node ID")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would change without writing"
    )

    parsed = parser.parse_args(args)

    try:
        trug_path = Path(parsed.trug_file).resolve()
        directory = trug_path.parent

        result = tupdate(
            directory=directory,
            node_id=parsed.node_id,
            set_values=parsed.set_values,
            node_type=parsed.node_type,
            parent_id=parsed.parent_id,
            dry_run=parsed.dry_run,
        )

        prefix = "[DRY RUN] " if result["dry_run"] else ""
        print(f"{prefix}Updated node: {parsed.node_id}")
        for change in result["changes"]:
            print(f"  {change}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tdelete_command.
def tdelete_command(args: Optional[list] = None) -> int:
    """Remove nodes and connected edges from a TRUG graph.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tdelete_command SHALL DELETE RECORD node AND RECORD edge THEN WRITE FILE folder_trug.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tdelete",
        description="Remove nodes and connected edges from a TRUG graph",
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("node_ids", nargs="+", help="One or more node IDs to delete")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without writing",
    )

    parsed = parser.parse_args(args)

    if not parsed.force and not parsed.dry_run:
        node_list = ", ".join(parsed.node_ids)
        answer = input(f"Delete node(s) {node_list}? [y/N] ")
        if answer.lower() not in ("y", "yes"):
            print("Aborted.")
            return 0

    try:
        trug_path = Path(parsed.trug_file).resolve()
        directory = trug_path.parent

        result = tdelete(
            directory=directory,
            node_ids=parsed.node_ids,
            dry_run=parsed.dry_run,
        )

        prefix = "[DRY RUN] " if result["dry_run"] else ""
        for node_id in result["deleted_nodes"]:
            print(f"{prefix}Deleted node: {node_id}")
        if result["deleted_edges"]:
            print(f"{prefix}Deleted {len(result['deleted_edges'])} connected edge(s):")
            for edge in result["deleted_edges"]:
                print(f"  {edge} (removed)")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tunlink_command.
def tunlink_command(args: Optional[list] = None) -> int:
    """Remove specific edges from a TRUG graph.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tunlink_command SHALL DELETE RECORD edge THEN WRITE FILE folder_trug.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tunlink", description="Remove specific edges from a TRUG graph"
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("--from", dest="from_id", help="Source node ID")
    parser.add_argument("--to", dest="to_id", help="Target node ID")
    parser.add_argument("--relation", help="Edge relation type to match")
    parser.add_argument(
        "--all",
        dest="remove_all",
        action="store_true",
        help="Remove all matching edges (from or to a node)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without writing",
    )

    parsed = parser.parse_args(args)

    try:
        trug_path = Path(parsed.trug_file).resolve()
        directory = trug_path.parent

        result = tunlink_standalone(
            directory=directory,
            from_id=parsed.from_id,
            to_id=parsed.to_id,
            relation=parsed.relation,
            remove_all=parsed.remove_all,
            dry_run=parsed.dry_run,
        )

        prefix = "[DRY RUN] " if result["dry_run"] else ""
        print(f"{prefix}Removed {len(result['removed_edges'])} edge(s):")
        for edge in result["removed_edges"]:
            print(f"  {edge} (removed)")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tdim_command.
def tdim_command(args: Optional[list] = None) -> int:
    """Manage dimensions in a TRUG graph.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tdim_command SHALL READ OR WRITE DATA dimension TO FILE folder_trug.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder dim", description="Manage dimensions in a TRUG graph",
        epilog=_EPILOGS["dim"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "action", choices=["add", "remove", "list", "set"], help="Dimension action"
    )
    parser.add_argument(
        "-C", "--directory", default=".", help="Directory containing folder.trug.json"
    )
    parser.add_argument("-n", "--name", help="Dimension name (for add/remove/set)")
    parser.add_argument(
        "-d", "--description", default="", help="Dimension description (for add)"
    )
    parser.add_argument(
        "--base-level", default="BASE", help="Base metric level (for add)"
    )
    parser.add_argument("--node", dest="node_id", help="Node ID (for set)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force removal even if nodes use the dimension",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for list (default: text)",
    )

    parsed = parser.parse_args(args)

    try:
        if parsed.action == "add":
            if not parsed.name:
                print("Error: --name required for add", file=sys.stderr)
                return 1
            tdim(
                parsed.directory,
                "add",
                name=parsed.name,
                description=parsed.description,
                base_level=parsed.base_level,
            )
            print(f"Added dimension: {parsed.name}")

        elif parsed.action == "remove":
            if not parsed.name:
                print("Error: --name required for remove", file=sys.stderr)
                return 1
            tdim(parsed.directory, "remove", name=parsed.name, force=parsed.force)
            print(f"Removed dimension: {parsed.name}")

        elif parsed.action == "list":
            result = tdim(parsed.directory, "list", format=parsed.format)
            if parsed.format == "json":
                print(json.dumps(result, indent=2))
            else:
                print(result)

        elif parsed.action == "set":
            if not parsed.node_id or not parsed.name:
                print("Error: --node and --name required for set", file=sys.stderr)
                return 1
            tdim(parsed.directory, "set", node_id=parsed.node_id, dimension=parsed.name)
            print(f"Set dimension '{parsed.name}' on node '{parsed.node_id}'")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION twatch_command.
def twatch_command(args: Optional[list] = None) -> int:
    """Watch folder.trug.json and auto-regenerate docs.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION twatch_command SHALL SCAN FILE folder_trug THEN RENDER DATA docs SUBJECT_TO file CHANGED.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs twatch",
        description="Watch folder.trug.json and regenerate docs on change",
    )
    parser.add_argument(
        "directory", nargs="?", default=".", help="Directory to watch (default: .)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0)",
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")

    parsed = parser.parse_args(args)

    try:
        print(f"Watching {parsed.directory} for changes...")
        results = twatch(
            directory=parsed.directory,
            interval=parsed.interval,
            once=parsed.once,
        )
        if parsed.once:
            for filename in sorted(results):
                print(f"  Rendered: {filename}")
        return 0
    except KeyboardInterrupt:
        print("\nStopped watching.")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION tsync_command.
def tsync_command(args: Optional[list] = None) -> int:
    """Synchronize folder.trug.json with directory contents.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION tsync_command SHALL SYNC FILE folder_trug TO DATA filesystem_state.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs tsync",
        description="Sync folder.trug.json with actual directory contents",
    )
    parser.add_argument(
        "directory", nargs="?", default=".", help="Directory to sync (default: .)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without modifying graph"
    )
    parser.add_argument(
        "--no-edges", action="store_true", help="Don't infer edges from file contents"
    )

    parsed = parser.parse_args(args)

    try:
        result = tsync(
            directory=parsed.directory,
            dry_run=parsed.dry_run,
            infer_edges=not parsed.no_edges,
        )

        prefix = "[DRY RUN] " if parsed.dry_run else ""

        added = result["added_nodes"]
        removed = result["removed_nodes"]
        edges = result["inferred_edges"]

        if added:
            print(f"{prefix}Added {len(added)} node(s):")
            for nid in added:
                print(f"  + {nid}")
        if removed:
            print(f"{prefix}Stale nodes (files removed): {len(removed)}")
            for nid in removed:
                print(f"  - {nid}")
        if edges:
            print(f"{prefix}Inferred {len(edges)} edge(s):")
            for e in edges:
                print(f"  {e['from_id']} --[{e['relation']}]--> {e['to_id']}")
        if not added and not removed and not edges:
            print(f"{prefix}Graph is in sync.")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

# AGENT claude SHALL DEFINE FUNCTION folder_check_command.
def folder_check_command(args: Optional[list] = None) -> int:
    """Validate folder.trug.json files for correctness and staleness.

    Returns:
        Exit code (0 = passed, 1 = errors found, 2 = runtime error)

    <trl>
    FUNCTION folder_check_command SHALL CHECK FILE folder_trug THEN EMIT DATA check_result.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder check",
        description="Validate folder.trug.json files against governance spec",
        epilog=_EPILOGS["check"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="folder.trug.json files or directories to check",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="scan_all",
        help="Check all folder.trug.json files in the repo",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show summary",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit code 1 if any warnings)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory for --all scanning (default: cwd)",
    )

    parsed = parser.parse_args(args)

    if not parsed.paths and not parsed.scan_all:
        parser.error("Provide PATHS or use --all")
        return 2  # pragma: no cover

    try:
        results = check_all(
            paths=parsed.paths if parsed.paths else None,
            scan_all=parsed.scan_all,
            root=parsed.root,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if not results:
        print("No folder.trug.json files found.", file=sys.stderr)
        return 2

    # Output
    if parsed.output_format == "json":
        print(format_json(results))
    else:
        print(format_text(results, quiet=parsed.quiet))

    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    if total_errors > 0:
        return 1
    if parsed.strict and total_warnings > 0:
        return 1
    return 0

# AGENT claude SHALL DEFINE FUNCTION folder_render_command.
def folder_render_command(args: Optional[list] = None) -> int:
    """Render ARCHITECTURE.md from folder.trug.json files.

    Returns:
        Exit code (0 = success, 1 = TRUG not found/invalid, 2 = write error)

    <trl>
    FUNCTION folder_render_command SHALL RENDER FILE folder_trug TO FILE architecture_md.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder render",
        description="Render ARCHITECTURE.md from folder.trug.json files",
        epilog=_EPILOGS["render"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to folder containing folder.trug.json, or to folder.trug.json itself",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="scan_all",
        help="Render ARCHITECTURE.md for all folders with folder.trug.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print to stdout instead of writing file",
    )
    parser.add_argument(
        "--output",
        default=None,
        dest="output",
        help="Write to custom path instead of ARCHITECTURE.md",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory for --all scanning (default: cwd)",
    )
    parser.add_argument(
        "--render-date",
        default=None,
        dest="render_date",
        help="Fixed date string for deterministic output (e.g. 2026-01-01)",
    )

    parsed = parser.parse_args(args)

    if not parsed.path and not parsed.scan_all:
        parser.error("Provide PATH or use --all")
        return 1  # pragma: no cover

    if parsed.scan_all:
        search_root = Path(parsed.root) if parsed.root else Path.cwd()
        trug_paths = _find_all_folder_trugs(search_root)
        if not trug_paths:
            print("No folder.trug.json files found.", file=sys.stderr)
            return 1
        count = 0
        for trug_path in trug_paths:
            try:
                content = render_architecture(
                    str(trug_path),
                    render_date=parsed.render_date,
                    repo_root=search_root,
                )
            except (ValueError, TypeError, KeyError) as e:
                print(f"Error rendering {trug_path}: {e}", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"Error rendering {trug_path}: {e}", file=sys.stderr)
                return 1
            if parsed.dry_run:
                print(f"--- {trug_path.parent} ---")
                print(content)
            else:
                out_path = trug_path.parent / "ARCHITECTURE.md"
                try:
                    out_path.write_text(content, encoding="utf-8")
                except OSError as e:
                    print(f"Error writing {out_path}: {e}", file=sys.stderr)
                    return 2
            count += 1
        if not parsed.dry_run:
            print(f"Rendered {count} ARCHITECTURE.md files")
        return 0
    else:
        # Single folder
        p = Path(parsed.path).resolve()
        if p.is_dir():
            trug_path = p / "folder.trug.json"
        elif p.name == "folder.trug.json":
            trug_path = p
        else:
            trug_path = p / "folder.trug.json"

        if not trug_path.exists():
            print(f"Error: {trug_path} not found", file=sys.stderr)
            return 1

        repo_root = Path(parsed.root) if parsed.root else Path.cwd()
        try:
            content = render_architecture(
                str(trug_path), render_date=parsed.render_date, repo_root=repo_root
            )
        except (ValueError, TypeError, KeyError) as e:
            print(f"Error rendering {trug_path}: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error rendering {trug_path}: {e}", file=sys.stderr)
            return 1

        if parsed.dry_run:
            print(content)
            return 0

        if parsed.output:
            out_path = Path(parsed.output)
        else:
            out_path = trug_path.parent / "ARCHITECTURE.md"

        try:
            out_path.write_text(content, encoding="utf-8")
        except OSError as e:
            print(f"Error writing {out_path}: {e}", file=sys.stderr)
            return 2

        print(f"Rendered {out_path}")
        return 0

# AGENT claude SHALL DEFINE FUNCTION folder_init_command.
def folder_init_command(args: Optional[list] = None) -> int:
    """Generate skeleton folder.trug.json from filesystem scanning.

    Returns:
        Exit code (0 = success, 1 = exists/invalid, 2 = write error)

    <trl>
    FUNCTION folder_init_command SHALL SCAN DATA filesystem THEN WRITE FILE folder_trug.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs-folder-init",
        description="Generate skeleton folder.trug.json from filesystem scanning",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to folder to scan",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="scan_all",
        help="Generate for all folders missing folder.trug.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print JSON to stdout instead of writing file",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing folder.trug.json",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        dest="no_tests",
        help="Skip pytest subprocess for test counting",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory for --all scanning (default: cwd)",
    )

    parsed = parser.parse_args(args)

    if not parsed.path and not parsed.scan_all:
        parser.error("Provide PATH or use --all")
        return 1  # pragma: no cover

    run_tests = not parsed.no_tests

    if parsed.scan_all:
        search_root = Path(parsed.root) if parsed.root else Path.cwd()
        folders = find_folders_without_trug(search_root)
        if not folders:
            print("No folders without folder.trug.json found.", file=sys.stderr)
            return 0
        count = 0
        for folder in folders:
            try:
                trug = init_folder_trug(
                    folder,
                    force=parsed.force,
                    run_tests=run_tests,
                )
            except (FileExistsError, NotADirectoryError) as e:
                print(f"Skipping {folder}: {e}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"Error scanning {folder}: {e}", file=sys.stderr)
                continue

            if parsed.dry_run:
                print(f"--- {folder} ---")
                print(json.dumps(trug, indent=2))
            else:
                out_path = folder / "folder.trug.json"
                try:
                    write_trug(trug, out_path)
                except OSError as e:
                    print(f"Error writing {out_path}: {e}", file=sys.stderr)
                    return 2
                print(f"Generated {out_path}")
            count += 1
        if not parsed.dry_run:
            print(f"Generated {count} folder.trug.json files")
        return 0
    else:
        # Single folder
        p = Path(parsed.path).resolve()
        if not p.is_dir():
            print(f"Error: not a directory: {p}", file=sys.stderr)
            return 1

        try:
            trug = init_folder_trug(p, force=parsed.force, run_tests=run_tests)
        except FileExistsError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except NotADirectoryError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

        if parsed.dry_run:
            print(json.dumps(trug, indent=2))
            return 0

        out_path = p / "folder.trug.json"
        try:
            write_trug(trug, out_path)
        except OSError as e:
            print(f"Error writing {out_path}: {e}", file=sys.stderr)
            return 2

        print(f"Generated {out_path}")
        return 0

# AGENT claude SHALL DEFINE FUNCTION folder_sync_command.
def folder_sync_command(args: Optional[list] = None) -> int:
    """Sync folder.trug.json with current filesystem state.

    Returns:
        Exit code (0 = success, 1 = no TRUG/invalid, 2 = write error)

    <trl>
    FUNCTION folder_sync_command SHALL SYNC FILE folder_trug TO DATA filesystem_state.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder sync",
        description="Sync folder.trug.json with current filesystem state",
        epilog=_EPILOGS["sync"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to folder to sync",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="scan_all",
        help="Sync all folders with existing folder.trug.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print diff to stdout instead of writing",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        dest="no_tests",
        help="Skip pytest subprocess for test counting",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory for --all scanning (default: cwd)",
    )
    parser.add_argument(
        "--prune-after",
        type=int,
        default=7,
        dest="prune_after",
        help="Remove nodes stale for N consecutive syncs (0 disables, default 7)",
    )

    parsed = parser.parse_args(args)

    if not parsed.path and not parsed.scan_all:
        parser.error("Provide PATH or use --all")
        return 1  # pragma: no cover

    run_tests = not parsed.no_tests

    if parsed.scan_all:
        search_root = Path(parsed.root) if parsed.root else Path.cwd()
        trug_files = _find_all_folder_trugs(search_root)
        if not trug_files:
            print("No folder.trug.json files found.", file=sys.stderr)
            return 0
        count = 0
        errors = 0
        for trug_file in trug_files:
            folder = trug_file.parent
            try:
                result = sync_folder_trug(
                    folder,
                    run_tests=run_tests,
                    dry_run=parsed.dry_run,
                    prune_after=parsed.prune_after,
                )
            except Exception as e:
                print(f"Error syncing {folder}: {e}", file=sys.stderr)
                errors += 1
                continue
            _print_sync_result(folder, result, parsed.dry_run)
            count += 1
        if not parsed.dry_run:
            msg = f"Synced {count} folder.trug.json files"
            if errors:
                msg += f" ({errors} errors)"
            print(msg)
        return 2 if errors else 0
    else:
        # Single folder
        p = Path(parsed.path).resolve()
        if not p.is_dir():
            print(f"Error: not a directory: {p}", file=sys.stderr)
            return 1

        try:
            result = sync_folder_trug(
                p,
                run_tests=run_tests,
                dry_run=parsed.dry_run,
                prune_after=parsed.prune_after,
            )
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except NotADirectoryError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

        _print_sync_result(p, result, parsed.dry_run)
        return 0

def _print_sync_result(folder: Path, result, dry_run: bool) -> None:
    """Print the sync result summary."""
    prefix = "[dry-run] " if dry_run else ""
    if not result.has_changes:
        print(f"{prefix}No changes: {folder}/folder.trug.json")
        return

    print(f"{prefix}Synced {folder}/folder.trug.json")
    for change in result.changes:
        print(f"  {change}")
    print(f"  Edges: {result.edges_added} added, {result.edges_total} total")

# AGENT claude SHALL DEFINE FUNCTION folder_map_command.
def folder_map_command(args: Optional[list] = None) -> int:
    """Build root-level graph from all folder.trug.json files.

    Returns:
        Exit code (0 = success, 1 = no TRUGs/invalid, 2 = write error)

    <trl>
    FUNCTION folder_map_command SHALL SCAN FILE folder_trug THEN BUILD RECORD root_graph.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs-folder-map",
        description="Build root-level graph from all folder.trug.json files",
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print JSON to stdout instead of writing file",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Custom output file path",
    )

    parsed = parser.parse_args(args)

    root = Path(parsed.root) if parsed.root else Path.cwd()
    if not root.is_dir():
        print(f"Error: not a directory: {root}", file=sys.stderr)
        return 1

    try:
        result = map_folder_trugs(
            root,
            dry_run=parsed.dry_run,
            output=parsed.output,
        )
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Write error: {e}", file=sys.stderr)
        return 2

    if parsed.dry_run and result.root_graph:
        print(json.dumps(result.root_graph, indent=2, ensure_ascii=False))

    for change in result.changes:
        print(change, file=sys.stderr)

    return 0

# AGENT claude SHALL DEFINE FUNCTION folder_export_command.
def folder_export_command(args: Optional[list] = None) -> int:
    """Export folder.trug.json from PostgreSQL database.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION folder_export_command SHALL READ DATA database THEN WRITE FILE folder_trug.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder export",
        description="Export folder.trug.json from PostgreSQL database",
        epilog=_EPILOGS["export"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to folder to export",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="export_all",
        help="Export all graphs from database",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory for --all scanning (default: cwd)",
    )

    parsed = parser.parse_args(args)

    if not parsed.path and not parsed.export_all:
        parser.error("Provide PATH or use --all")
        return 1

    from trugs_store.persistence.dual_write import export_trug

    if parsed.export_all:
        search_root = Path(parsed.root) if parsed.root else Path.cwd()
        trug_files = _find_all_folder_trugs(search_root)
        count = 0
        for trug_file in trug_files:
            try:
                exported = export_trug(trug_file)
                if exported:
                    print(f"Exported {trug_file}")
                    count += 1
                else:
                    print(f"Skipped {trug_file} (not in database)", file=sys.stderr)
            except Exception as e:
                print(f"Error exporting {trug_file}: {e}", file=sys.stderr)
        print(f"Exported {count} folder.trug.json files")
        return 0
    else:
        p = Path(parsed.path).resolve()
        trug_file = p / "folder.trug.json" if p.is_dir() else p
        try:
            exported = export_trug(trug_file)
            if exported:
                print(f"Exported {trug_file}")
                return 0
            else:
                print(f"Graph not found in database for {trug_file}", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

# AGENT claude SHALL DEFINE FUNCTION folder_import_command.
def folder_import_command(args: Optional[list] = None) -> int:
    """Import folder.trug.json into PostgreSQL database.

    Returns:
        Exit code (0 = success, 1 = error)

    <trl>
    FUNCTION folder_import_command SHALL READ FILE folder_trug THEN WRITE DATA database.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug-a-folder import",
        description="Import folder.trug.json into PostgreSQL database",
        epilog=_EPILOGS["import"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to folder to import",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="import_all",
        help="Import all folder.trug.json files",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory for --all scanning (default: cwd)",
    )

    parsed = parser.parse_args(args)

    if not parsed.path and not parsed.import_all:
        parser.error("Provide PATH or use --all")
        return 1

    from trugs_store.persistence.dual_write import import_trug

    if parsed.import_all:
        search_root = Path(parsed.root) if parsed.root else Path.cwd()
        trug_files = _find_all_folder_trugs(search_root)
        count = 0
        for trug_file in trug_files:
            try:
                import_trug(trug_file)
                print(f"Imported {trug_file}")
                count += 1
            except Exception as e:
                print(f"Error importing {trug_file}: {e}", file=sys.stderr)
        print(f"Imported {count} folder.trug.json files")
        return 0
    else:
        p = Path(parsed.path).resolve()
        trug_file = p / "folder.trug.json" if p.is_dir() else p
        try:
            import_trug(trug_file)
            print(f"Imported {trug_file}")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

# ---------------------------------------------------------------------------
# trug-a-folder dispatch — the commons cartography verb set (manifest #2358).
# render is restricted to the `architecture` target; agent/claude/aaa renders
# are T3 system verbs and live on the `tg` binary, not here.
# ---------------------------------------------------------------------------

def _carto_render(argv):
    """trug-a-folder render [architecture] — commons render is architecture-only."""
    target = argv[0] if argv else "architecture"
    rest = argv[1:] if argv else []
    if target in ("-h", "--help", "help"):
        # Route to the architecture renderer's argparse help — the only
        # commons render target, so its help IS the verb's help.
        return folder_render_command(["--help"])
    if target == "architecture":
        return folder_render_command(rest)
    print(
        f"trug-a-folder render: unknown target '{target}' "
        "(commons render supports only 'architecture'; "
        "agent/claude/aaa renders are system verbs on `tg')",
        flush=True,
    )
    return 2


_FOLDER_DISPATCH = {
    "init": lambda argv: tinit_command(argv),
    "check": lambda argv: folder_check_command(argv),
    "sync": lambda argv: folder_sync_command(argv),
    "render": _carto_render,
    "info": lambda argv: info_command(argv),
    "ls": lambda argv: tls_command(argv),
    "where": lambda argv: twhere_command(argv),
    "find": lambda argv: tfind_command(argv),
    "add": lambda argv: tadd_command(argv),
    "mv": lambda argv: tmove_command(argv),
    "link": lambda argv: tlink_command(argv),
    "dim": lambda argv: tdim_command(argv),
    "export": lambda argv: folder_export_command(argv),
    "import": lambda argv: folder_import_command(argv),
}

# One-line verb summaries for the top-level banner (A4, STANDARD_cli_help.md).
# Keys MUST mirror _FOLDER_DISPATCH — test_help_bar.py asserts the two agree.
_FOLDER_SUMMARIES = {
    "init": "Initialize folder.trug.json in a directory",
    "check": "Validate folder.trug.json against the governance rules",
    "sync": "Reconcile folder.trug.json with the filesystem",
    "render": "Render ARCHITECTURE.md from folder.trug.json",
    "info": "Show summary information about a TRUG file",
    "ls": "List directory contents with TRUG metadata",
    "where": "Search all folder graphs for a concept, node, or file",
    "find": "Query nodes in a TRUG graph by type/name/dimension",
    "add": "Add files to the TRUG graph",
    "mv": "Move/rename a node in the TRUG graph",
    "link": "Create or remove typed edges between nodes",
    "dim": "Manage dimensions in a TRUG graph",
    "export": "Export folder.trug.json from the database",
    "import": "Import folder.trug.json into the database",
}


def main(argv=None) -> int:
    """trug-a-folder entry point — cartography verbs only (T3-free)."""
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("trug-a-folder — TRUGS cartography (filesystem <-> TRUG graph)\n")
        print("usage: trug-a-folder <verb> [args...]\n")
        print("verbs:")
        for verb, summary in _FOLDER_SUMMARIES.items():
            print(f"  {verb:<12} {summary}")
        print("\nRun 'trug-a-folder <verb> --help' for verb-specific usage and examples.")
        return 0
    cmd, rest = argv[0], argv[1:]
    handler = _FOLDER_DISPATCH.get(cmd)
    if handler is None:
        print(
            f"trug-a-folder: unknown verb '{cmd}' "
            f"(expected one of: {', '.join(_FOLDER_DISPATCH)})",
            flush=True,
        )
        return 2
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
