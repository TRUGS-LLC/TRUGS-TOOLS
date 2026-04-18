"""Command-line interface for TRUGS tools."""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

from trugs_tools import __version__, __codename__
from trugs_tools.validator import validate_trug
from trugs_tools.generator import generate_trug, SUPPORTED_BRANCHES
from trugs_tools.renderer import render_all, render_architecture
from trugs_tools.filesystem.folder_check import find_all_folder_trugs as _find_all_folder_trugs
from trugs_tools.filesystem.tinit import tinit
from trugs_tools.filesystem.tadd import tadd
from trugs_tools.filesystem.tls import tls
from trugs_tools.filesystem.tcd import tcd
from trugs_tools.filesystem.tfind import tfind
from trugs_tools.filesystem.tmove import tmove
from trugs_tools.filesystem.tlink import tlink, tunlink, VALID_RELATIONS
from trugs_tools.filesystem.tget import tget
from trugs_tools.filesystem.tupdate import tupdate
from trugs_tools.filesystem.tdelete import tdelete
from trugs_tools.epic_sync import epic_sync_command
from trugs_tools.filesystem.tunlink import tunlink as tunlink_standalone
from trugs_tools.filesystem.tdim import tdim
from trugs_tools.filesystem.twatch import twatch
from trugs_tools.filesystem.tsync import tsync
from trugs_tools.filesystem.twhere import twhere
from trugs_tools.filesystem.folder_check import (
    check_all,
    check_folder_trug,
    format_json,
    format_text,
)
from trugs_tools.filesystem.folder_init import (
    init_folder_trug,
    find_folders_without_trug,
)
from trugs_tools.filesystem.folder_sync import sync_folder_trug
from trugs_tools.filesystem.folder_map import map_folder_trugs
from trugs_store.persistence.dual_write import write_trug


# AGENT claude SHALL DEFINE FUNCTION validate_command.
def validate_command(args: Optional[list] = None) -> int:
    """Validate TRUG files.
    
    Returns:
        Exit code (0 = valid, 1 = invalid, 2 = error)
    """
    parser = argparse.ArgumentParser(
        prog="trugs-validate",
        description="Validate TRUG files against TRUGS v1.0 specification"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="TRUG file(s) to validate"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only show summary"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show all details"
    )
    
    parsed_args = parser.parse_args(args)
    
    all_valid = True
    results = []
    
    for filepath in parsed_args.files:
        try:
            result = validate_trug(filepath)
            results.append((filepath, result))
            
            if not result.valid:
                all_valid = False
            
            # Print results
            if parsed_args.format == "text":
                if not parsed_args.quiet:
                    print(f"\n{filepath}:")
                    print(f"  {result}")
                    
                    if parsed_args.verbose or not result.valid:
                        for error in result.errors:
                            print(f"  ❌ {error}")
                        
                        if parsed_args.verbose:
                            for warning in result.warnings:
                                print(f"  ⚠️  {warning}")
            
        except FileNotFoundError:
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {filepath}: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Error validating {filepath}: {e}", file=sys.stderr)
            return 2
    
    # Summary
    if parsed_args.format == "text" and len(results) > 1:
        valid_count = sum(1 for _, r in results if r.valid)
        print(f"\n{'='*60}")
        print(f"Summary: {valid_count}/{len(results)} files valid")
        print(f"{'='*60}")
    
    # JSON output
    if parsed_args.format == "json":
        output = {
            "results": [
                {
                    "file": str(filepath),
                    "valid": result.valid,
                    "errors": [e.to_dict() for e in result.errors],
                    "warnings": [w.to_dict() for w in result.warnings],
                }
                for filepath, result in results
            ]
        }
        print(json.dumps(output, indent=2))
    
    return 0 if all_valid else 1


# AGENT claude SHALL DEFINE FUNCTION generate_command.
def generate_command(args: Optional[list] = None) -> int:
    """Generate example TRUG files.
    
    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        prog="trugs-generate",
        description="Generate example TRUG files"
    )
    parser.add_argument(
        "-b", "--branch",
        required=True,
        choices=list(SUPPORTED_BRANCHES.keys()),
        help="Branch to generate"
    )
    parser.add_argument(
        "-t", "--template",
        choices=["minimal", "complete"],
        default="minimal",
        help="Template type (default: minimal)"
    )
    parser.add_argument(
        "-e", "--extension",
        action="append",
        dest="extensions",
        help="Add extension (can be specified multiple times)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation of generated TRUG"
    )
    
    parsed_args = parser.parse_args(args)
    
    try:
        trug = generate_trug(
            branch=parsed_args.branch,
            template=parsed_args.template,
            extensions=parsed_args.extensions,
            validate=not parsed_args.no_validate
        )
        
        # Output
        output_json = json.dumps(trug, indent=2, ensure_ascii=False)
        
        if parsed_args.output:
            with open(parsed_args.output, 'w', encoding='utf-8') as f:
                f.write(output_json)
            print(f"Generated {parsed_args.branch} TRUG: {parsed_args.output}", file=sys.stderr)
        else:
            print(output_json)
        
        return 0
        
    except Exception as e:
        print(f"Error generating TRUG: {e}", file=sys.stderr)
        return 1


# AGENT claude SHALL DEFINE FUNCTION info_command.
def info_command(args: Optional[list] = None) -> int:
    """Show information about TRUG files.
    
    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        prog="trugs-info",
        description="Show information about TRUG files"
    )
    parser.add_argument(
        "file",
        help="TRUG file to analyze"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
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
        node_types = {}
        for node in trug.get("nodes", []):
            node_type = node.get("type", "Unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        info["node_types"] = node_types
        
        # Count edge relations
        edge_relations = {}
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
            
            if info['extensions']:
                print(f"Extensions: {', '.join(info['extensions'])}")
            
            if info['node_types']:
                print("\nNode Types:")
                for node_type, count in sorted(info['node_types'].items()):
                    print(f"  {node_type}: {count}")
            
            if info['edge_relations']:
                print("\nEdge Relations:")
                for relation, count in sorted(info['edge_relations'].items()):
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


# AGENT claude SHALL DEFINE FUNCTION render_command.
def render_command(args: Optional[list] = None) -> int:
    """Render folder.trug.json into deterministic markdown files.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        prog="trugs-render",
        description="Render folder.trug.json into AAA.md, README.md, and ARCHITECTURE.md"
    )
    parser.add_argument(
        "file",
        help="Path to folder.trug.json"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory (default: same directory as input file)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rendered content without writing files"
    )
    parser.add_argument(
        "--file-type",
        choices=["aaa", "readme", "architecture", "all"],
        default="all",
        help="Which file(s) to render (default: all)"
    )

    parsed_args = parser.parse_args(args)

    try:
        input_path = Path(parsed_args.file)
        if not input_path.exists():
            print(f"Error: File not found: {parsed_args.file}", file=sys.stderr)
            return 1

        output_dir = parsed_args.output or str(input_path.parent)

        with open(input_path, 'r', encoding='utf-8') as f:
            trug = json.load(f)

        results = render_all(trug)

        # Filter by file type if specified
        if parsed_args.file_type != "all":
            key_map = {"aaa": "AAA.md", "readme": "README.md", "architecture": "ARCHITECTURE.md"}
            selected_key = key_map[parsed_args.file_type]
            results = {selected_key: results[selected_key]}

        if parsed_args.dry_run:
            for filename, content in sorted(results.items()):
                print(f"=== {filename} ===")
                print(content)
                print()
        else:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            for filename, content in sorted(results.items()):
                filepath = out / filename
                filepath.write_text(content, encoding='utf-8')
                print(f"  Rendered: {filepath}")

        return 0

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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tinit",
        description="Initialize folder.trug.json in a directory"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Target directory (default: current directory)"
    )
    parser.add_argument(
        "-n", "--name",
        help="Project name (default: directory name)"
    )
    parser.add_argument(
        "-d", "--description",
        default="",
        help="Project description"
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan directory for existing files"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing folder.trug.json"
    )
    parser.add_argument(
        "-q", "--qualifying-interest",
        default=None,
        help="Hub qualifying interest (what this TRUG curates)"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tadd",
        description="Add files to the TRUG graph"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Files to add"
    )
    parser.add_argument(
        "-C", "--directory",
        default=".",
        help="Directory containing folder.trug.json (default: .)"
    )
    parser.add_argument(
        "-t", "--type",
        dest="node_type",
        help="Override inferred node type"
    )
    parser.add_argument(
        "-p", "--parent",
        dest="parent_id",
        help="Parent node ID"
    )
    parser.add_argument(
        "--purpose",
        default="",
        help="Purpose description for added nodes"
    )

    parsed = parser.parse_args(args)

    try:
        result = tadd(
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tls",
        description="List directory contents with TRUG metadata"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to list (default: .)"
    )
    parser.add_argument(
        "--node",
        dest="node_id",
        help="List children of specific node"
    )
    parser.add_argument(
        "--edges",
        action="store_true",
        help="Show edge details"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tcd",
        description="Navigate the TRUG graph"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="/",
        help="Target node ID, '..' for parent, '/' for root"
    )
    parser.add_argument(
        "-C", "--directory",
        default=".",
        help="Directory containing folder.trug.json"
    )
    parser.add_argument(
        "--current",
        help="Current node ID (needed for '..' navigation)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tfind",
        description="Query nodes in a TRUG graph"
    )
    parser.add_argument(
        "-C", "--directory",
        default=".",
        help="Directory containing folder.trug.json"
    )
    parser.add_argument(
        "-t", "--type",
        dest="node_type",
        help="Filter by node type"
    )
    parser.add_argument(
        "-n", "--name",
        dest="name_pattern",
        help="Filter by name (regex pattern)"
    )
    parser.add_argument(
        "-d", "--dimension",
        help="Filter by dimension"
    )
    parser.add_argument(
        "-e", "--edge-relation",
        help="Filter by edge relation"
    )
    parser.add_argument(
        "-m", "--metric-level",
        help="Filter by metric level"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs twhere",
        description="Search across all folder.trug.json files for a concept, node, or file"
    )
    parser.add_argument(
        "query",
        help="Search term (regex supported)"
    )
    parser.add_argument(
        "-C", "--directory",
        default=".",
        help="Root directory to search from (default: current)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
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
                path_info = f" → {r['file_path']}" if r['file_path'] else ""
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tmove",
        description="Move/rename a node in the TRUG graph"
    )
    parser.add_argument(
        "node_id",
        help="Node ID to move/rename"
    )
    parser.add_argument(
        "-C", "--directory",
        default=".",
        help="Directory containing folder.trug.json"
    )
    parser.add_argument(
        "--name",
        dest="new_name",
        help="New filename"
    )
    parser.add_argument(
        "--parent",
        dest="new_parent_id",
        help="New parent node ID"
    )

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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tlink",
        description="Create or remove typed edges between nodes"
    )
    parser.add_argument(
        "from_id",
        help="Source node ID"
    )
    parser.add_argument(
        "to_id",
        help="Target node ID"
    )
    parser.add_argument(
        "-r", "--relation",
        required=True,
        help=f"Edge relation type ({', '.join(sorted(VALID_RELATIONS))})"
    )
    parser.add_argument(
        "-C", "--directory",
        default=".",
        help="Directory containing folder.trug.json"
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the edge instead of creating it"
    )
    parser.add_argument(
        "-w", "--weight",
        type=float,
        default=None,
        help="Edge weight (0.0-1.0): curator endorsement strength"
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
            print(f"Removed edge: {parsed.from_id} --[{parsed.relation}]--> {parsed.to_id}")
        else:
            tlink(
                directory=parsed.directory,
                from_id=parsed.from_id,
                to_id=parsed.to_id,
                relation=parsed.relation,
                weight=parsed.weight,
            )
            if parsed.weight is not None:
                print(f"Created edge: {parsed.from_id} --[{parsed.relation}, {parsed.weight}]--> {parsed.to_id}")
            else:
                print(f"Created edge: {parsed.from_id} --[{parsed.relation}]--> {parsed.to_id}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# AGENT claude SHALL DEFINE FUNCTION tget_command.
def tget_command(args: Optional[list] = None) -> int:
    """Read full content of a specific node.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tget",
        description="Read full content of a specific node in a TRUG graph"
    )
    parser.add_argument(
        "trug_file",
        help="Path to .trug.json file"
    )
    parser.add_argument(
        "node_id",
        help="ID of node to read"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--edges",
        action="store_true",
        help="Also show connected edges"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tupdate",
        description="Update properties on an existing node in a TRUG graph"
    )
    parser.add_argument(
        "trug_file",
        help="Path to .trug.json file"
    )
    parser.add_argument(
        "node_id",
        help="ID of node to update"
    )
    parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        help="Set property: key=value (repeatable)"
    )
    parser.add_argument(
        "--type",
        dest="node_type",
        help="Change node type"
    )
    parser.add_argument(
        "--parent",
        dest="parent_id",
        help="Change parent node ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tdelete",
        description="Remove nodes and connected edges from a TRUG graph"
    )
    parser.add_argument(
        "trug_file",
        help="Path to .trug.json file"
    )
    parser.add_argument(
        "node_ids",
        nargs="+",
        help="One or more node IDs to delete"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without writing"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tunlink",
        description="Remove specific edges from a TRUG graph"
    )
    parser.add_argument(
        "trug_file",
        help="Path to .trug.json file"
    )
    parser.add_argument(
        "--from",
        dest="from_id",
        help="Source node ID"
    )
    parser.add_argument(
        "--to",
        dest="to_id",
        help="Target node ID"
    )
    parser.add_argument(
        "--relation",
        help="Edge relation type to match"
    )
    parser.add_argument(
        "--all",
        dest="remove_all",
        action="store_true",
        help="Remove all matching edges (from or to a node)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without writing"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tdim",
        description="Manage dimensions in a TRUG graph"
    )
    parser.add_argument(
        "action",
        choices=["add", "remove", "list", "set"],
        help="Dimension action"
    )
    parser.add_argument(
        "-C", "--directory",
        default=".",
        help="Directory containing folder.trug.json"
    )
    parser.add_argument(
        "-n", "--name",
        help="Dimension name (for add/remove/set)"
    )
    parser.add_argument(
        "-d", "--description",
        default="",
        help="Dimension description (for add)"
    )
    parser.add_argument(
        "--base-level",
        default="BASE",
        help="Base metric level (for add)"
    )
    parser.add_argument(
        "--node",
        dest="node_id",
        help="Node ID (for set)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force removal even if nodes use the dimension"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for list (default: text)"
    )

    parsed = parser.parse_args(args)

    try:
        if parsed.action == "add":
            if not parsed.name:
                print("Error: --name required for add", file=sys.stderr)
                return 1
            tdim(parsed.directory, "add", name=parsed.name,
                 description=parsed.description,
                 base_level=parsed.base_level)
            print(f"Added dimension: {parsed.name}")

        elif parsed.action == "remove":
            if not parsed.name:
                print("Error: --name required for remove", file=sys.stderr)
                return 1
            tdim(parsed.directory, "remove", name=parsed.name,
                 force=parsed.force)
            print(f"Removed dimension: {parsed.name}")

        elif parsed.action == "list":
            result = tdim(parsed.directory, "list", format=parsed.format)
            if parsed.format == "json":
                print(json.dumps(result, indent=2))
            else:
                print(result)

        elif parsed.action == "set":
            if not parsed.node_id or not parsed.name:
                print("Error: --node and --name required for set",
                      file=sys.stderr)
                return 1
            tdim(parsed.directory, "set", node_id=parsed.node_id,
                 dimension=parsed.name)
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs twatch",
        description="Watch folder.trug.json and regenerate docs on change"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to watch (default: .)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit"
    )

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
    """
    parser = argparse.ArgumentParser(
        prog="trugs tsync",
        description="Sync folder.trug.json with actual directory contents"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to sync (default: .)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying graph"
    )
    parser.add_argument(
        "--no-edges",
        action="store_true",
        help="Don't infer edges from file contents"
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs-folder-check",
        description="Validate folder.trug.json files against governance spec",
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs-folder-render",
        description="Render ARCHITECTURE.md from folder.trug.json files",
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
                    str(trug_path), render_date=parsed.render_date, repo_root=search_root
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
                    folder, force=parsed.force, run_tests=run_tests,
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs-folder-sync",
        description="Sync folder.trug.json with current filesystem state",
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
                    folder, run_tests=run_tests, dry_run=parsed.dry_run,
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
                p, run_tests=run_tests, dry_run=parsed.dry_run,
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


# AGENT claude SHALL DEFINE FUNCTION aaa_generate_command.
def aaa_generate_command(args: Optional[list] = None) -> int:
    """Generate AAA.md files from GitHub Issues by folder label.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    from trugs_tools.aaa_generator import generate_all

    parser = argparse.ArgumentParser(
        prog="trugs-aaa-generate",
        description="Generate AAA.md from GitHub Issues",
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Repository root directory",
    )

    parsed = parser.parse_args(args)

    try:
        generate_all(parsed.root)
        return 0
    except Exception as e:
        print(f"Error generating AAA.md files: {e}", file=sys.stderr)
        return 1


# AGENT claude SHALL DEFINE FUNCTION agent_render_command.
def agent_render_command(args: Optional[list] = None) -> int:
    """Render .github/agent_instructions.trug.json to .github/copilot-instructions.md.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    from trugs_tools.agent_instructions_renderer import render_agent_instructions

    parser = argparse.ArgumentParser(
        prog="trugs-agent-render",
        description="Render agent_instructions.trug.json to copilot-instructions.md",
    )
    parser.add_argument(
        "--input",
        default=".github/agent_instructions.trug.json",
        help="Path to agent_instructions.trug.json (default: .github/agent_instructions.trug.json)",
    )
    parser.add_argument(
        "--output",
        default=".github/copilot-instructions.md",
        help="Path to write copilot-instructions.md (default: .github/copilot-instructions.md)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output to stdout instead of writing to file",
    )

    parsed = parser.parse_args(args)

    input_path = Path(parsed.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        content = render_agent_instructions(input_path)
    except Exception as e:
        print(f"Error rendering agent instructions: {e}", file=sys.stderr)
        return 1

    if parsed.dry_run:
        print(content, end="")
        return 0

    output_path = Path(parsed.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


# AGENT claude SHALL DEFINE FUNCTION claude_render_command.
def claude_render_command(args: Optional[list] = None) -> int:
    """Render .github/agent_instructions.trug.json to CLAUDE.md.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    from trugs_tools.claude_instructions_renderer import render_claude_instructions

    parser = argparse.ArgumentParser(
        prog="trugs-claude-render",
        description="Render agent_instructions.trug.json to CLAUDE.md",
    )
    parser.add_argument(
        "--input",
        default=".github/agent_instructions.trug.json",
        help="Path to agent_instructions.trug.json (default: .github/agent_instructions.trug.json)",
    )
    parser.add_argument(
        "--output",
        default="CLAUDE.md",
        help="Path to write CLAUDE.md (default: CLAUDE.md)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output to stdout instead of writing to file",
    )

    parsed = parser.parse_args(args)

    input_path = Path(parsed.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        content = render_claude_instructions(input_path)
    except Exception as e:
        print(f"Error rendering Claude instructions: {e}", file=sys.stderr)
        return 1

    if parsed.dry_run:
        print(content, end="")
        return 0

    output_path = Path(parsed.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


# AGENT claude SHALL DEFINE FUNCTION folder_export_command.
def folder_export_command(args: Optional[list] = None) -> int:
    """Export folder.trug.json from PostgreSQL database.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        prog="trugs-folder-export",
        description="Export folder.trug.json from PostgreSQL database",
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
    """
    parser = argparse.ArgumentParser(
        prog="trugs-folder-import",
        description="Import folder.trug.json into PostgreSQL database",
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


def _invoke(handler_qualname: str, args=None):
    """Delegate to a handler; handler_qualname is module:function, e.g. 'memory:main'."""
    import importlib, sys as _sys
    if args is None:
        args = _sys.argv[2:]
    mod_name, fn_name = handler_qualname.split(':')
    try:
        mod = importlib.import_module(f'trugs_tools.{mod_name}')
    except ImportError:
        mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name)
    # Most legacy handlers accept argv slice positionally
    try:
        return fn(args)
    except TypeError:
        # Some handlers read sys.argv themselves — swap it in
        saved = _sys.argv[:]
        _sys.argv = ['handler'] + list(args or [])
        try:
            return fn() or 0
        finally:
            _sys.argv = saved


def _dispatch_memory(argv):
    """tg memory <sub> [args...] — delegates to trugs_tools.memory.main with sub prepended."""
    # memory.py's CLI reads sys.argv; we pass argv as-is (sub becomes first positional)
    return _invoke('memory:main', argv)


def _dispatch_aaa(argv):
    """tg aaa <sub> [args...]"""
    if not argv:
        print("tg aaa: expected subcommand (generate|validate)", flush=True)
        return 2
    sub, rest = argv[0], argv[1:]
    if sub == 'validate':
        return _invoke('aaa_validator:main', rest)
    elif sub == 'generate':
        return aaa_generate_command(rest)
    else:
        print(f"tg aaa: unknown subcommand '{sub}' (expected: generate, validate)", flush=True)
        return 2


def _dispatch_epic(argv):
    """tg epic <sub> [args...]"""
    if not argv:
        print("tg epic: expected subcommand (sync)", flush=True)
        return 2
    sub, rest = argv[0], argv[1:]
    if sub == 'sync':
        return epic_sync_command(rest)
    else:
        print(f"tg epic: unknown subcommand '{sub}' (expected: sync)", flush=True)
        return 2


def _dispatch_render(argv):
    """tg render [target] — default 'architecture'."""
    target = argv[0] if argv else 'architecture'
    rest = argv[1:] if argv else []
    if target == 'architecture':
        return folder_render_command(rest)
    elif target == 'agent':
        # agent_instructions_renderer has its own entry point
        return _invoke('agent_instructions_renderer:main', rest)
    elif target == 'claude':
        return _invoke('claude_instructions_renderer:main', rest)
    elif target == 'aaa':
        return aaa_generate_command(rest)
    else:
        print(f"tg render: unknown target '{target}' (expected: architecture, agent, claude, aaa)", flush=True)
        return 2


# Unified tg dispatch table — maps top-level verb → callable taking argv list
_TG_DISPATCH = {
    # Lifecycle
    'init':        lambda argv: tinit_command(argv),
    'check':       lambda argv: folder_check_command(argv),
    'sync':        lambda argv: folder_sync_command(argv),
    'render':      _dispatch_render,
    'validate':    lambda argv: _invoke('validate:main', argv),
    # Inspection
    'info':        lambda argv: info_command(argv),
    'ls':          lambda argv: tls_command(argv),
    'where':       lambda argv: twhere_command(argv),
    'find':        lambda argv: tfind_command(argv),
    # CRUD
    'add':         lambda argv: tadd_command(argv),
    'get':         lambda argv: _invoke('tget:main', argv),
    'update':      lambda argv: _invoke('tupdate:main', argv),
    'delete':      lambda argv: _invoke('tdelete:main', argv),
    'mv':          lambda argv: tmove_command(argv),
    'link':        lambda argv: tlink_command(argv),
    'unlink':      lambda argv: _invoke('tunlink:main', argv),
    'dim':         lambda argv: tdim_command(argv),
    # Special
    'compliance':  lambda argv: _invoke('compliance_check:main', argv),
    'trl':         lambda argv: _invoke('trl:main', argv),
    'export':      lambda argv: folder_export_command(argv) if 'folder_export_command' in globals() else (print('tg export: not yet wired'), 2)[1],
    'import':      lambda argv: folder_import_command(argv) if 'folder_import_command' in globals() else (print('tg import: not yet wired'), 2)[1],
    # Sub-namespaces
    'memory':      _dispatch_memory,
    'aaa':         _dispatch_aaa,
    'epic':        _dispatch_epic,
}


_TG_HELP = """tg — TRUGS unified CLI

usage:  tg <command> [args...]

LIFECYCLE
  init [DIR]              create folder.trug.json in cwd or DIR
  check [PATH]            validate TRUG
  sync [PATH]             sync TRUG with filesystem reality
  render [TARGET]         render TRUG; TARGET ∈ {architecture|agent|claude|aaa} (default: architecture)
  validate [PATH]         CORE 16-rule structural validator

INSPECTION
  info NODE               show node metadata + edges
  ls [SCOPE]              list nodes in TRUG
  where NODE              locate node (path, parents, scope)
  find PATTERN            search nodes by name/property

CRUD
  add NODE                create node
  get NODE                read node
  update NODE             update node properties
  delete NODE             delete node
  mv SRC DST              rename/move node
  link A B --as REL       create edge
  unlink A B              delete edge
  dim NODE [--set K=V]    show/set dimensions

SPECIAL
  compliance [PATH]       Dark Code compliance scan
  trl FILE                TRL compile/lint
  export PATH             TRUG → archive
  import PATH             archive → TRUG

SUB-NAMESPACES
  memory <sub>            memory graph — remember, recall, forget, associate, render, audit, import, reconcile
  aaa <sub>               AAA protocol — generate, validate
  epic <sub>              EPIC — sync

Use `tg <command> --help` for command-specific help.
"""


# AGENT claude SHALL DEFINE FUNCTION main.
def main() -> int:
    """tg — unified TRUGS CLI. Dispatches top-level verb to the appropriate handler.
    
    Differs from the legacy flat multi-binary layout (trugs-folder-check, trugs-memory, etc.)
    by exposing a single `tg` binary with git-style nested subparsers.
    """
    argv = sys.argv[1:]
    
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(_TG_HELP)
        return 0
    
    if argv[0] in ('--version', '-V'):
        print(f"tg (trugs-tools) {__version__} ({__codename__})")
        raise SystemExit(0)
    
    cmd = argv[0]
    rest = argv[1:]
    
    handler = _TG_DISPATCH.get(cmd)
    if handler is None:
        print(f"tg: unknown command '{cmd}'. Run 'tg --help' for usage.", flush=True)
        return 2
    
    result = handler(rest)
    return result if isinstance(result, int) else (0 if result is None else 1)


if __name__ == "__main__":
    sys.exit(main())
