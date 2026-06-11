# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""tget — Read full content of a specific node from a TRUG file.

Usage:
    trugs-tget graph.trug.json node_id
    trugs-tget graph.trug.json node_id --format json
    trugs-tget graph.trug.json node_id --edges

Note: this is the explicit-TRUG-file CRUD command (the live ``tg get`` verb,
operating on a named ``*.trug.json``). It is distinct from the namesake
``trugs_folder.tget``, which is the folder-graph operation over a
directory's ``folder.trug.json``. The two are intentionally separate command
families, not duplicates (AAA #2190 SP1 disposition: retained).

<trl>
PROCESS tget SHALL LOAD FILE trug_json THEN RETURN DATA node SUBJECT_TO node_id MATCH.
</trl>
"""

import argparse
import json
import sys
from typing import Any, List, Optional


# PROCESS loader SHALL READ FILE path THEN RETURN RECORD graph.
def load_trug(path: str) -> dict:
    """Load a TRUG JSON file.

    <trl>
    FUNCTION load_trug SHALL READ FILE path THEN RETURN RECORD graph.
    </trl>
    """
    with open(path) as f:
        return json.load(f)


# PROCESS finder SHALL MATCH RECORD node FROM RECORD graph.
def find_node(trug: dict, node_id: str) -> Optional[dict]:
    """Find a node by ID.

    <trl>
    FUNCTION find_node SHALL FILTER RECORD graph THEN RETURN RECORD node SUBJECT_TO id MATCH.
    </trl>
    """
    for node in trug.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


# PROCESS finder SHALL FILTER ALL RECORD edge FROM RECORD graph.
def find_edges(trug: dict, node_id: str) -> List[dict]:
    """Find all edges connected to a node (incoming and outgoing).

    <trl>
    FUNCTION find_edges SHALL FILTER ALL RECORD edge FROM RECORD graph THEN RETURN DATA edge_list.
    </trl>
    """
    edges = []
    for edge in trug.get("edges", []):
        if edge.get("from_id") == node_id or edge.get("to_id") == node_id:
            edges.append(edge)
    return edges


# PROCESS formatter SHALL MAP RECORD node TO STRING DATA output.
def format_text(node: dict, edges: Optional[List[dict]] = None) -> str:
    """Format node as human-readable text.

    <trl>
    FUNCTION format_text SHALL MAP RECORD node TO DATA text THEN APPEND DATA edge_list SUBJECT_TO edges NOT NULL.
    </trl>
    """
    lines = [f"Node: {node['id']}"]
    for field in ["type", "parent_id", "contains", "metric_level", "dimension"]:
        val = node.get(field)
        if val is not None:
            lines.append(f"  {field}: {val}")

    props = node.get("properties", {})
    if props:
        lines.append("  properties:")
        for k, v in props.items():
            if isinstance(v, (dict, list)):
                lines.append(f"    {k}: {json.dumps(v, indent=6)}")
            else:
                lines.append(f"    {k}: {v}")

    if edges is not None:
        lines.append(f"\nEdges ({len(edges)}):")
        for e in edges:
            rel = e.get("relation", "?")
            weight = e.get("weight")
            w_str = f" w:{weight}" if weight is not None else ""
            if e.get("from_id") == node["id"]:
                lines.append(f"  {node['id']} --[{rel}{w_str}]--> {e['to_id']}")
            else:
                lines.append(f"  {e['from_id']} --[{rel}{w_str}]--> {node['id']}")

    return "\n".join(lines)


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main(argv: Optional[list] = None) -> int:
    """CLI entry point: parse arguments, load TRUG file, locate node, and emit output.

    <trl>
    FUNCTION main SHALL PARSE DATA argv THEN LOAD FILE trug_json THEN RETURN INTEGER exit_code.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trugs-tget",
        description="Read full content of a specific node from a TRUG file.",
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("node_id", help="ID of the node to read")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--edges", action="store_true", help="Also show connected edges"
    )

    args = parser.parse_args(argv)

    try:
        trug = load_trug(args.trug_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    node = find_node(trug, args.node_id)
    if node is None:
        print(f"Error: node '{args.node_id}' not found", file=sys.stderr)
        return 1

    edges = find_edges(trug, args.node_id) if args.edges else None

    if args.format == "json":
        out: dict[str, Any] = {"node": node}
        if edges is not None:
            out["edges"] = edges
        print(json.dumps(out, indent=2))
    else:
        print(format_text(node, edges))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
