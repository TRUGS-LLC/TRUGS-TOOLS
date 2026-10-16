# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""tdelete — Remove a node and all its connected edges from a TRUG file.

Usage:
    trugs-tdelete graph.trug.json node_id
    trugs-tdelete graph.trug.json node_id --dry-run
    trugs-tdelete graph.trug.json node_id1 node_id2 node_id3
    trugs-tdelete graph.trug.json node_id --force

Note: this is the explicit-TRUG-file CRUD command (the live ``tg delete`` verb,
operating on a named ``*.trug.json``). It is distinct from the namesake
``trugs_folder.tdelete``, which is the folder-graph operation over a
directory's ``folder.trug.json``. The two are intentionally separate command
families, not duplicates (AAA (private reference removed) SP1 disposition: retained).

Note: deleting a node repairs the hierarchy on both sides of the link. Stripping
the deleted ids from every surviving ``contains[]`` is only half of it — the
deleted node's children still carry ``parent_id`` pointing at a node that no
longer exists, which rule_3 reports as ``DANGLING_PARENT_ID`` ((private reference removed)).
Each orphan is therefore re-attached to its nearest surviving ancestor, and
added to that ancestor's ``contains[]``; an orphan with no surviving ancestor
becomes a root (``parent_id: null``, in no ``contains[]``). A delete that
leaves a VALID graph INVALID is not a delete, it is a corruption.

<trl>
PROCESS tdelete SHALL READ RECORD node FROM FILE trug_json THEN DELETE RECORD node AND ALL EDGE connected TO RECORD node THEN WRITE RECORD parent_id TO ALL RECORD orphan.
</trl>
"""

import argparse
import json
import sys
from typing import Optional


def load_trug(path: str) -> dict:
    """Load and parse a TRUG JSON file from disk.

    <trl>
    FUNCTION load_trug SHALL READ FILE path THEN RETURN RECORD graph.
    </trl>
    """
    with open(path) as f:
        return json.load(f)


def save_trug(path: str, trug: dict) -> None:
    """Serialize and write a TRUG graph dict to a JSON file with trailing newline.

    <trl>
    FUNCTION save_trug SHALL WRITE RECORD graph TO FILE path.
    </trl>
    """
    with open(path, "w") as f:
        json.dump(trug, f, indent=2)
        f.write("\n")


def nearest_surviving_ancestor(
    start_id: str, node_map: dict, deleted: set
) -> Optional[str]:
    """Walk up parent_id from a deleted node to the first ancestor that survives.

    Returns that ancestor's id, or None when the chain runs out — which is the
    signal that the orphan becomes a root.

    <trl>
    FUNCTION nearest_surviving_ancestor SHALL READ RECORD node THEN RETURN DATA ancestor_id.
    </trl>
    """
    # `seen` is the bound, not a nicety. A parent cycle is precisely the
    # corruption class this release repairs, so the walk must assume it can be
    # handed one: if every node on a ring is deleted in the same invocation, an
    # unbounded walk spins forever and `trug delete` hangs instead of failing.
    seen = {start_id}
    current = start_id
    while True:
        parent = node_map.get(current, {}).get("parent_id")
        if not isinstance(parent, str) or parent not in node_map:
            # A root (None), a non-string parent_id (rule_7's to report), or a
            # reference to a node this graph does not contain. All three mean the
            # same thing here: there is no ancestor left to inherit. Adopting a
            # reference that does not resolve would swap one DANGLING_PARENT_ID
            # for another, so the orphan is promoted to a root instead.
            return None
        if parent not in deleted:
            return parent
        if parent in seen:
            return None
        seen.add(parent)
        current = parent


def plan_reparenting(nodes: list, deleted: set) -> list:
    """Compute the (orphan_id, new_parent_id) pairs a deletion would create.

    Every surviving node whose parent is being deleted is re-attached to its
    nearest surviving ancestor; new_parent_id is None when none survives. The
    walk is transitive over the whole deleted set, so deleting a parent and its
    own child in one invocation still lands the grandchildren correctly.

    <trl>
    FUNCTION plan_reparenting SHALL READ RECORD node THEN RETURN DATA reparented.
    </trl>
    """
    node_map = {n.get("id"): n for n in nodes if n.get("id") is not None}
    reparented = []
    for node in nodes:
        nid = node.get("id")
        if nid is None or nid in deleted:
            # An id-less node is rule_6's MISSING_REQUIRED_FIELD, not this
            # command's to fix: it cannot be named in a contains[] and cannot be
            # looked up to be rewritten, so re-parenting it is not defined. It is
            # skipped rather than crashed on — 2.2.0 deleted around such a node
            # and exited 0, and a hierarchy repair must not turn that into a
            # traceback. A deleted node, likewise, has no hierarchy left to repair.
            continue
        parent = node.get("parent_id")
        if not isinstance(parent, str) or parent not in deleted:
            continue
        ancestor = nearest_surviving_ancestor(parent, node_map, deleted)
        if ancestor == nid:
            # Only reachable when the input already contains a parent cycle that
            # runs through this very node: the orphan is its own ancestor. Writing
            # it back would trade DANGLING_PARENT_ID for HIERARCHY_CYCLE, so the
            # orphan is promoted to a root instead. A delete may inherit the
            # graph's corruption; it may not author new corruption of its own.
            ancestor = None
        reparented.append((nid, ancestor))
    return reparented


def format_reparent_target(new_parent: Optional[str]) -> str:
    """Render a re-parenting destination for the CLI report.

    <trl>
    FUNCTION format_reparent_target SHALL READ DATA new_parent THEN RETURN DATA label.
    </trl>
    """
    return new_parent if new_parent else "(no surviving ancestor — becomes a root)"


def _readopt_edge(edges: list, removed: list, orphan_id: str, new_parent: str) -> None:
    """Re-issue the orphan's containment edge from its adopter.

    ``contains[]`` and the containment EDGE are two halves of one fact. Repairing
    only the array leaves a graph the CORE validator calls VALID while
    ``trug-a-folder check`` rejects it — "Contains-array lists 'x' but no
    'contains' edge from 'y' to 'x' exists" — which is the same shape of
    half-maintained link this whole repair exists to close, reintroduced one
    layer down. The sibling repair in ``trugs_folder.folder_sync`` writes both;
    these two must not disagree about what adoption means.

    The re-issued edge is a COPY OF THE ONE JUST REMOVED with its ``from_id``
    moved to the adopter, rather than a freshly minted literal. Edge shape is a
    property of the graph, not of this command: folder graphs carry ``weight``
    and ``properties`` on every edge and use the lowercase ``contains``, while a
    hand-written TRUG may carry the three CORE fields and an uppercase relation.
    Copying inherits whichever convention the file already keeps.

    When the deleted parent held no containment edge to this orphan, nothing is
    added. A graph that expressed containment only through ``contains[]`` does
    not acquire an edge list it never had — a delete may repair what it broke,
    and may not author structure the author declined to write.

    <trl>
    FUNCTION readopt_edge SHALL READ RECORD edge THEN WRITE RECORD edge TO DATA edges.
    </trl>
    """
    template = next(
        (
            e
            for e in removed
            if e.get("to_id") == orphan_id
            and str(e.get("relation", "")).lower() == "contains"
        ),
        None,
    )
    if template is None:
        return
    readopted = dict(template)
    readopted["from_id"] = new_parent
    if readopted not in edges:
        edges.append(readopted)


def main(argv: Optional[list] = None) -> int:
    """CLI entry point: parse args, delete nodes and edges, repair the hierarchy, return exit code.

    <trl>
    FUNCTION main SHALL PARSE DATA argv THEN DELETE RECORD node AND RECORD edge FROM FILE trug_json THEN WRITE RECORD parent_id TO RECORD orphan THEN RETURN DATA exit_code.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="trug delete",
        description="Remove a node and all its connected edges from a TRUG file.",
        epilog="""examples:
  trug delete graph.trug.json my_node --dry-run
  trug delete graph.trug.json my_node other_node --force

hierarchy:
  Children of a deleted node are re-attached to its nearest surviving ancestor
  and added to that ancestor's contains[]. An orphan with no surviving ancestor
  becomes a root (parent_id: null).

exit codes:
  0  success
  1  node not found / file error
  2  usage error (bad flags or arguments)""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("trug_file", help="Path to .trug.json file")
    parser.add_argument("node_ids", nargs="+", help="One or more node IDs to delete")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without writing",
    )
    # This command has never prompted, so there is no confirmation to skip. The
    # flag is still accepted — non-interactive callers pass it today and must keep
    # exiting 0 — but it is documented as the no-op it is rather than advertising
    # a prompt that does not exist ((private reference removed)). Adding the prompt instead
    # would silently change the exit behaviour of every scripted caller.
    parser.add_argument(
        "--force",
        action="store_true",
        help="No-op, accepted for compatibility (this command never prompts)",
    )

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

    # Plan the hierarchy repair. Computed from the pre-deletion `nodes` because the
    # ancestor walk needs the deleted nodes' own parent_id links to climb through.
    reparenting = plan_reparenting(nodes, node_ids_set)

    if args.dry_run:
        print(f"Dry run — would delete from '{args.trug_file}':")
        for nid in args.node_ids:
            print(f"  Node: {nid}")
        for edge in edges_to_remove:
            print(
                f"  Edge: {edge.get('from_id')} --[{edge.get('relation')}]--> {edge.get('to_id')}"
            )
        for parent_id, removed in contains_updates:
            print(f"  Contains: remove {removed} from {parent_id}")
        for orphan_id, new_parent in reparenting:
            print(f"  Reparent: {orphan_id} -> {format_reparent_target(new_parent)}")
        return 0

    # Remove nodes
    trug["nodes"] = [n for n in nodes if n.get("id") not in node_ids_set]

    # Remove connected edges
    trug["edges"] = [e for e in edges if e not in edges_to_remove]

    # Update parent contains arrays
    for node in trug["nodes"]:
        contains = node.get("contains", [])
        node["contains"] = [c for c in contains if c not in node_ids_set]

    # Re-parent the orphans. This runs AFTER the strip above, so an id appended
    # here cannot be stripped back out, and every surviving node is known to carry
    # a list-valued contains[] by the time it is appended to.
    surviving_map = {n.get("id"): n for n in trug["nodes"] if n.get("id") is not None}
    for orphan_id, new_parent in reparenting:
        surviving_map[orphan_id]["parent_id"] = new_parent
        if new_parent is None:
            continue
        contains = surviving_map[new_parent]["contains"]
        # A grandparent that already listed the grandchild alongside the deleted
        # parent must not end up listing it twice — rule_3 walks contains[] entry
        # by entry, so a duplicate is a second diagnosis of a link that is fine.
        if orphan_id not in contains:
            contains.append(orphan_id)
        _readopt_edge(trug["edges"], edges_to_remove, orphan_id, new_parent)

    save_trug(args.trug_file, trug)

    print(f"Deleted from '{args.trug_file}':")
    for nid in args.node_ids:
        print(f"  Node: {nid}")
    if edges_to_remove:
        print(f"  Edges removed: {len(edges_to_remove)}")
        for edge in edges_to_remove:
            print(
                f"    {edge.get('from_id')} --[{edge.get('relation')}]--> {edge.get('to_id')}"
            )
    if reparenting:
        print(f"  Reparented: {len(reparenting)} orphan(s)")
        for orphan_id, new_parent in reparenting:
            print(f"    {orphan_id} -> {format_reparent_target(new_parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
