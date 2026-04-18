"""tunlink — Remove a specific edge from a TRUG file.

Usage:
    trugs-tunlink graph.trug.json --from source_id --to target_id
    trugs-tunlink graph.trug.json --from source_id --to target_id --relation REFERENCES
    trugs-tunlink graph.trug.json --from source_id --all
    trugs-tunlink graph.trug.json --to target_id --all
    trugs-tunlink graph.trug.json --from source_id --to target_id --dry-run
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
        prog="trugs-tunlink",
        description="Remove a specific edge from a TRUG file.",
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("--from", dest="from_id",
                        help="Source node ID")
    parser.add_argument("--to", dest="to_id",
                        help="Target node ID")
    parser.add_argument("--relation",
                        help="Edge relation type to match")
    parser.add_argument("--all", action="store_true",
                        help="Remove all matching edges")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be removed without writing")

    args = parser.parse_args(argv)

    if not args.from_id and not args.to_id:
        print("Error: provide --from and/or --to", file=sys.stderr)
        return 1

    if not args.from_id and not args.all:
        print("Error: --from required unless using --all with --to", file=sys.stderr)
        return 1

    if not args.to_id and not args.all:
        print("Error: --to required unless using --all with --from", file=sys.stderr)
        return 1

    try:
        trug = load_trug(args.trug_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    edges = trug.get("edges", [])

    # Find matching edges
    to_remove = []
    for edge in edges:
        match = True
        if args.from_id and edge.get("from_id") != args.from_id:
            match = False
        if args.to_id and edge.get("to_id") != args.to_id:
            match = False
        if args.relation and edge.get("relation") != args.relation:
            match = False
        if match:
            to_remove.append(edge)

    if not to_remove:
        print("Error: no matching edge found", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Dry run — would remove {len(to_remove)} edge(s):")
        for e in to_remove:
            rel = e.get("relation", "?")
            print(f"  {e.get('from_id')} --[{rel}]--> {e.get('to_id')}")
        return 0

    # Remove edges
    trug["edges"] = [e for e in edges if e not in to_remove]

    save_trug(args.trug_file, trug)

    print(f"Removed {len(to_remove)} edge(s):")
    for e in to_remove:
        rel = e.get("relation", "?")
        print(f"  {e.get('from_id')} --[{rel}]--> {e.get('to_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
