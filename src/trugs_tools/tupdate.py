"""tupdate — Update properties on an existing node in a TRUG file.

Usage:
    trugs-tupdate graph.trug.json node_id --set key=value
    trugs-tupdate graph.trug.json node_id --set name="New Name" --set confidence=0.8
    trugs-tupdate graph.trug.json node_id --type ENTITY
    trugs-tupdate graph.trug.json node_id --parent new_parent_id
    trugs-tupdate graph.trug.json node_id --set key=value --dry-run
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional


# PROCESS loader SHALL READ FILE path THEN RETURN RECORD graph.
def load_trug(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# PROCESS saver SHALL WRITE RECORD graph TO FILE path.
def save_trug(path: str, trug: dict) -> None:
    with open(path, "w") as f:
        json.dump(trug, f, indent=2)
        f.write("\n")


# PROCESS parser SHALL MAP STRING DATA input TO RECORD value.
def parse_value(raw: str) -> Any:
    """Infer type from string value."""
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.lower() == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# PROCESS updater SHALL WRITE RECORD value TO RECORD node.
def set_nested(d: dict, key: str, value: Any) -> None:
    """Set a value using dot notation (e.g., 'metadata.source')."""
    parts = key.split(".")
    for part in parts[:-1]:
        if part not in d or not isinstance(d[part], dict):
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trugs-tupdate",
        description="Update properties on an existing node in a TRUG file.",
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("node_id", help="ID of the node to update")
    parser.add_argument("--set", action="append", metavar="KEY=VALUE",
                        help="Set a property (repeatable)")
    parser.add_argument("--type", dest="new_type",
                        help="Change node type")
    parser.add_argument("--parent", dest="new_parent",
                        help="Change parent_id")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show changes without writing")

    args = parser.parse_args(argv)

    if not args.set and not args.new_type and not args.new_parent:
        print("Error: provide --set, --type, or --parent", file=sys.stderr)
        return 1

    try:
        trug = load_trug(args.trug_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Find the node
    node = None
    for n in trug.get("nodes", []):
        if n.get("id") == args.node_id:
            node = n
            break

    if node is None:
        print(f"Error: node '{args.node_id}' not found", file=sys.stderr)
        return 1

    changes = []

    # Apply --set
    if args.set:
        props = node.setdefault("properties", {})
        for kv in args.set:
            if "=" not in kv:
                print(f"Error: invalid --set format '{kv}', expected KEY=VALUE", file=sys.stderr)
                return 1
            key, raw_value = kv.split("=", 1)
            value = parse_value(raw_value)
            old = props.get(key)
            set_nested(props, key, value)
            changes.append(f"  properties.{key}: {old!r} → {value!r}")

    # Apply --type
    if args.new_type:
        old = node.get("type")
        node["type"] = args.new_type
        changes.append(f"  type: {old!r} → {args.new_type!r}")

    # Apply --parent (maintains bidirectional hierarchy)
    if args.new_parent:
        old_parent_id = node.get("parent_id")
        node_id = node.get("id")

        # Remove from old parent's contains[]
        if old_parent_id:
            for n in trug.get("nodes", []):
                if n.get("id") == old_parent_id:
                    contains = n.get("contains", [])
                    if node_id in contains:
                        contains.remove(node_id)
                    break

        # Set new parent_id
        new_parent = args.new_parent if args.new_parent != "null" else None
        node["parent_id"] = new_parent

        # Add to new parent's contains[]
        if new_parent:
            for n in trug.get("nodes", []):
                if n.get("id") == new_parent:
                    contains = n.get("contains", [])
                    if node_id not in contains:
                        contains.append(node_id)
                    break
            else:
                print(f"Warning: new parent '{new_parent}' not found", file=sys.stderr)

        changes.append(f"  parent_id: {old_parent_id!r} → {new_parent!r}")

    if args.dry_run:
        print(f"Dry run — changes to node '{args.node_id}':")
        for c in changes:
            print(c)
        return 0

    save_trug(args.trug_file, trug)
    print(f"Updated node '{args.node_id}':")
    for c in changes:
        print(c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
