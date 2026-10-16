# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""tupdate — Update properties on an existing node in a TRUG file.

Usage:
    trugs-tupdate graph.trug.json node_id --set key=value
    trugs-tupdate graph.trug.json node_id --set name="New Name" --set confidence=0.8
    trugs-tupdate graph.trug.json node_id --type ENTITY
    trugs-tupdate graph.trug.json node_id --parent new_parent_id
    trugs-tupdate graph.trug.json node_id --parent null
    trugs-tupdate graph.trug.json node_id --set key=value --dry-run

Note: this is the explicit-TRUG-file CRUD command (the live ``tg update`` verb,
operating on a named ``*.trug.json``). It is distinct from the namesake
``trugs_folder.tupdate``, which is the folder-graph operation over a
directory's ``folder.trug.json``. The two are intentionally separate command
families, not duplicates (AAA (private reference removed) SP1 disposition: retained).

<trl>
PROCESS tupdate SHALL LOAD RECORD graph FROM FILE trug_json THEN WRITE DATA property TO RECORD node SUBJECT_TO VALID RECORD parent_id AND SAVE FILE trug_json.
</trl>
"""

import argparse
import json
import sys
from typing import Any, Optional


# PROCESS loader SHALL READ FILE path THEN RETURN RECORD graph.
def load_trug(path: str) -> dict:
    """Read a TRUG JSON file from disk and return it as a dict.

    <trl>
    FUNCTION load_trug SHALL READ FILE path THEN RETURN RECORD graph.
    </trl>
    """
    with open(path) as f:
        return json.load(f)


# PROCESS saver SHALL WRITE RECORD graph TO FILE path.
def save_trug(path: str, trug: dict) -> None:
    """Serialise a TRUG graph dict to a JSON file, with trailing newline.

    <trl>
    FUNCTION save_trug SHALL WRITE RECORD graph TO FILE path.
    </trl>
    """
    with open(path, "w") as f:
        json.dump(trug, f, indent=2)
        f.write("\n")


# PROCESS parser SHALL MAP STRING DATA input TO RECORD value.
def parse_value(raw: str) -> Any:
    """Infer type from string value: boolean, null, int, float, or string.

    <trl>
    FUNCTION parse_value SHALL MAP DATA raw_string TO RECORD value SUBJECT_TO TYPE_INFERENCE.
    </trl>
    """
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
    """Set a value using dot notation (e.g., 'metadata.source'), creating intermediate dicts as needed.

    <trl>
    FUNCTION set_nested SHALL WRITE RECORD value TO RECORD node SUBJECT_TO DOT_NOTATION key.
    </trl>
    """
    parts = key.split(".")
    for part in parts[:-1]:
        if part not in d or not isinstance(d[part], dict):
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value


# PROCESS validator SHALL READ RECORD parent_id FROM RECORD graph THEN RETURN RECORD cycle.
def cycle_from_reparent(
    node_map: dict, node_id: str, new_parent_id: str
) -> Optional[list]:
    """Return the parent_id ring a re-parent would close, or None if it is safe.

    Walks upward from the PROPOSED parent. Reaching ``node_id`` means the
    proposal names the node itself or one of its descendants, so the re-parent
    would close a cycle; the returned list is that ring, read as child -> parent
    and ending back on ``node_id`` — the same shape rule_3's HIERARCHY_CYCLE
    reports. Walking parent_id alone is sufficient here for the same reason it
    is sufficient there: contains[] must point back at its child's parent_id, so
    a cycle through contains[] appears in the parent chain too.

    The walk is bounded by the set of ids already visited, so a graph that
    ALREADY contains a cycle terminates instead of spinning — re-parenting a
    node OUT of such a cycle is exactly the repair --parent exists to make, and
    it must not hang.

    <trl>
    FUNCTION cycle_from_reparent SHALL READ RECORD parent_id FROM RECORD graph BOUNDED THEN RETURN RECORD cycle.
    </trl>
    """
    ring = [node_id]
    seen: set = set()
    cur: Any = new_parent_id
    while isinstance(cur, str) and cur not in seen:
        ring.append(cur)
        if cur == node_id:
            return ring
        seen.add(cur)
        ancestor = node_map.get(cur)
        cur = ancestor.get("parent_id") if ancestor is not None else None
    # Either we reached a root (parent_id None/absent, or a dangling reference),
    # or we re-entered a pre-existing ring that does not pass through node_id —
    # not ours to report, and not a reason to refuse this re-parent.
    return None


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main(argv: Optional[list] = None) -> int:
    """CLI entry point: parse arguments, locate the target node, apply updates, and write the result.

    <trl>
    FUNCTION main SHALL PARSE DATA argv THEN WRITE DATA property TO RECORD node SUBJECT_TO VALID RECORD parent_id THEN RETURN INTEGER exit_code.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug update",
        description="Update properties on an existing node in a TRUG file.",
        epilog="""examples:
  trug update graph.trug.json my_node --set status=done
  trug update graph.trug.json my_node --type DOCUMENT --dry-run

exit codes:
  0  success
  1  node or new parent not found / re-parent would create a hierarchy cycle
     / file error
  2  usage error (bad flags or arguments)""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("node_id", help="ID of the node to update")
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="Set a property (repeatable)",
    )
    parser.add_argument("--type", dest="new_type", help="Change node type")
    parser.add_argument("--parent", dest="new_parent", help="Change parent_id")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing"
    )

    args = parser.parse_args(argv)

    if not args.set and not args.new_type and not args.new_parent:
        print("Error: provide --set, --type, or --parent", file=sys.stderr)
        return 1

    try:
        trug = load_trug(args.trug_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Index the graph once: the node lookup, the --parent existence check, and
    # the ancestor walk all resolve ids against this one map. First id wins, so a
    # graph with duplicate ids resolves to the same node the old scan-and-break
    # loops reached. Non-string ids are skipped rather than keyed (an unhashable
    # id would otherwise raise here); they matched nothing before either.
    node_map: dict = {}
    for n in trug.get("nodes", []):
        nid = n.get("id")
        if isinstance(nid, str) and nid not in node_map:
            node_map[nid] = n

    # Find the node
    node = node_map.get(args.node_id)

    if node is None:
        print(f"Error: node '{args.node_id}' not found", file=sys.stderr)
        return 1

    # ─── validate everything BEFORE touching `trug` ──────────────────────────
    # Every refusal below returns while the graph is still pristine. The old code
    # removed the node from its OLD parent's contains[] before it checked
    # anything about the new one, so a refusal left a half-re-parented graph in
    # memory — harmless only because nothing had been saved yet, and a trap for
    # the next editor who moves a save earlier or adds a second write.

    if args.set:
        for kv in args.set:
            if "=" not in kv:
                print(
                    f"Error: invalid --set format '{kv}', expected KEY=VALUE",
                    file=sys.stderr,
                )
                return 1

    # `--parent null` detaches the node to root. It names no node, so neither the
    # existence check nor the cycle check applies to it.
    new_parent = None
    if args.new_parent:
        new_parent = args.new_parent if args.new_parent != "null" else None

    if new_parent is not None:
        if new_parent not in node_map:
            # Previously a warning: the re-parent was written anyway and left a
            # DANGLING_PARENT_ID behind, with exit 0 to say it went fine.
            print(f"Error: new parent '{new_parent}' not found", file=sys.stderr)
            return 1

        ring = cycle_from_reparent(node_map, args.node_id, new_parent)
        if ring is not None:
            # Previously not checked at all: `--parent <self>` exited 0 without
            # even a warning and wrote a HIERARCHY_CYCLE into the file.
            print(
                f"Error: new parent '{new_parent}' is node '{args.node_id}' or one "
                f"of its descendants; re-parenting would create a hierarchy cycle: "
                f"{' -> '.join(ring)}",
                file=sys.stderr,
            )
            return 1

    # ─── apply ───────────────────────────────────────────────────────────────

    changes = []

    # Apply --set
    if args.set:
        props = node.setdefault("properties", {})
        for kv in args.set:
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

        # Remove from old parent's contains[]. The isinstance guard keeps a
        # malformed parent_id (rule_7's to report, not ours) from reaching a dict
        # lookup: an unhashable one would raise here, where the old scan-and-
        # compare merely matched nothing.
        if isinstance(old_parent_id, str) and old_parent_id:
            old_parent = node_map.get(old_parent_id)
            if old_parent is not None:
                contains = old_parent.get("contains", [])
                if node_id in contains:
                    contains.remove(node_id)

        # Set new parent_id (`new_parent` was resolved and checked above)
        node["parent_id"] = new_parent

        # Add to new parent's contains[] — existence is already proven, so there
        # is no not-found branch left to fall through to.
        #
        # The result is assigned BACK rather than mutated in place. `.get(k, [])`
        # on a parent carrying no `contains` key hands back a fresh list, and
        # appending to it drops the reciprocal link on the floor: the child gets
        # its parent_id and the parent never learns it has a child, which reads
        # as INCONSISTENT_HIERARCHY. Only reachable on input that is already
        # INVALID (rule_6 requires the key), but silently losing half of the very
        # link this block exists to maintain is not the behaviour to have there.
        if new_parent:
            parent_node = node_map[new_parent]
            contains = parent_node.get("contains")
            if not isinstance(contains, list):
                contains = []
            if node_id not in contains:
                contains.append(node_id)
            parent_node["contains"] = contains

            # Move the containment EDGE to follow the node. contains[] and the
            # edge are two halves of one fact, and re-parenting maintained only
            # the array — so a moved node kept an edge from the parent it had
            # left and had none from the parent it had joined. The CORE validator
            # does not read edges for hierarchy, which is why this survived; the
            # folder-graph checker does, and reports it.
            #
            # The existing edge is RETARGETED, not replaced by a fresh literal,
            # so whatever shape the graph gives its edges is preserved. A graph
            # that expressed containment only through contains[] gains no edge —
            # re-parenting repairs the link it moved, and authors nothing new.
            for edge in trug.get("edges", []):
                if (
                    edge.get("to_id") == node_id
                    and edge.get("from_id") == old_parent_id
                    and str(edge.get("relation", "")).lower() == "contains"
                ):
                    edge["from_id"] = new_parent
                    break

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
