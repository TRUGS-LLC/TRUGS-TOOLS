"""tdelete — Remove a node and all its connected edges from a TRUG file.

Usage:
    trugs-tdelete graph.trug.json node_id
    trugs-tdelete graph.trug.json node_id --dry-run
    trugs-tdelete graph.trug.json node_id1 node_id2 node_id3
    trugs-tdelete graph.trug.json node_id --force
"""

import argparse
import json
import sys
from typing import Optional


# PROCESS loader SHALL READ FILE path THEN RETURN RECORD graph.
def load_trug(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# PROCESS saver SHALL WRITE RECORD graph TO FILE path.
def save_trug(path: str, trug: dict) -> None:
    with open(path, "w") as f:
        json.dump(trug, f, indent=2)
        f.write("\n")


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trugs-tdelete",
        description="Remove a node and all its connected edges from a TRUG file.",
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("node_ids", nargs="+", help="One or more node IDs to delete")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be deleted without writing")
    parser.add_argument("--force", action="store_true",
                        help="Skip confirmation")

    args = parser.parse_args(argv)

    try:
        trug = load_trug(args.trug_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    nodes = trug.get("nodes", [])
    edges = trug.get("edges", [])
    node_ids_set = set(args.node_ids)

    # Verify all nodes exist
    existing_ids = {n.get("id") for n in nodes}
    missing = node_ids_set - existing_ids
    if missing:
        print(f"Error: node(s) not found: {', '.join(missing)}", file=sys.stderr)
        return 1

    # Find edges to remove
    edges_to_remove = []
    for edge in edges:
        if edge.get("from_id") in node_ids_set or edge.get("to_id") in node_ids_set:
            edges_to_remove.append(edge)

    # Update parent contains arrays
    contains_updates = []
    for node in nodes:
        contains = node.get("contains", [])
        removed = [c for c in contains if c in node_ids_set]
        if removed:
            contains_updates.append((node["id"], removed))

    if args.dry_run:
        print(f"Dry run — would delete from '{args.trug_file}':")
        for nid in args.node_ids:
            print(f"  Node: {nid}")
        for e in edges_to_remove:
            print(f"  Edge: {e.get('from_id')} --[{e.get('relation')}]--> {e.get('to_id')}")
        for parent_id, removed in contains_updates:
            print(f"  Contains: remove {removed} from {parent_id}")
        return 0

    # Remove nodes
    trug["nodes"] = [n for n in nodes if n.get("id") not in node_ids_set]

    # Remove connected edges
    trug["edges"] = [e for e in edges if e not in edges_to_remove]

    # Update parent contains arrays
    for node in trug["nodes"]:
        contains = node.get("contains", [])
        node["contains"] = [c for c in contains if c not in node_ids_set]

    save_trug(args.trug_file, trug)

    print(f"Deleted from '{args.trug_file}':")
    for nid in args.node_ids:
        print(f"  Node: {nid}")
    if edges_to_remove:
        print(f"  Edges removed: {len(edges_to_remove)}")
        for e in edges_to_remove:
            print(f"    {e.get('from_id')} --[{e.get('relation')}]--> {e.get('to_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
