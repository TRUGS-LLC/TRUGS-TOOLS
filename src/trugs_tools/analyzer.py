# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""TrugAnalyzer — structural graph analysis for any TRUG.

Provides 8 static analysis methods over TrugGraph:
  - find_unreachable_nodes: BFS from roots via hierarchy + semantic edges
  - find_dead_nodes: nodes not referenced by any edge to_id or contains[]
  - dominator_tree: iterative dataflow from hierarchy roots
  - impact_set / dependency_set: semantic reachability excluding the start node
  - complexity: cyclomatic + structural metrics
  - critical_path: longest root-to-leaf semantic path; root-reachable cycles raise
  - find_stale_propagation: transitively affected nodes from stale sources

All methods are stateless static methods. No mutation of TrugGraph.

Issue: (private reference removed)

<trl>
PROCESS analyzer SHALL COMPUTE DATA metrics FROM RECORD graph AND SHALL RETURN RESULT TO COMPONENT truganalyzer.
</trl>
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from trugs_tools.trug_graph import TrugGraph


# AGENT claude SHALL DEFINE RECORD trugcomplexitymetrics AS RECORD class.
@dataclass(frozen=True)
class TrugComplexityMetrics:
    """Structural complexity metrics for a TRUG.

    Attributes:
        cyclomatic: M = E - N + 2P (semantic edges, all nodes, connected components).
        branching_factor: Average outgoing semantic edges per node with outgoing edges.
        max_depth: Deepest containment path from root to leaf (node count).
        edge_density: Semantic edges / nodes (0.0 if no nodes).
        node_count: Total number of nodes.
        edge_count: Number of semantic edges (excludes contains).

    <trl>
    RECORD TrugComplexityMetrics SHALL REPRESENT DATA metrics AND SHALL CONTAIN DATA cyclomatic AND DATA edge_density AND DATA max_depth.
    </trl>
    """

    cyclomatic: int
    branching_factor: float
    max_depth: int
    edge_density: float
    node_count: int
    edge_count: int


# Relations that propagate staleness.
_STALE_PROPAGATION_RELATIONS = frozenset(
    {
        "uses",
        "implements",
        "produces",
        "depends_on",
    }
)


# AGENT claude SHALL DEFINE RECORD truganalyzer AS RECORD class.
class TrugAnalyzer:
    """Static analysis of TrugGraph structure. All methods are stateless.

    <trl>
    RECORD TrugAnalyzer SHALL COMPUTE DATA analysis FROM RECORD graph AND SHALL RETURN RESULT reachability AND RESULT dominators AND RESULT metrics.
    </trl>
    """

    # AGENT claude SHALL DEFINE FUNCTION find_unreachable_nodes.
    @staticmethod
    def find_unreachable_nodes(graph: TrugGraph) -> set[str]:
        """Nodes not reachable from any root via hierarchy OR semantic edges.

        BFS from all root_nodes() through:
          1. Containment: parent → children (contains[])
          2. Semantic edges: all non-contains edges (both directions)

        Cross-folder edge targets (containing ':') are skipped.
        Complexity: O(V+E).
        """
        all_ids = graph.node_ids()
        if not all_ids:
            return set()

        roots = graph.root_nodes()
        if not roots:
            return set(all_ids)

        # Build combined adjacency (hierarchy + semantic, both directions)
        adj: dict[str, set[str]] = {nid: set() for nid in all_ids}

        # Hierarchy: parent → children
        for nid in all_ids:
            for child in graph.get_children(nid):
                if child in adj:
                    adj[nid].add(child)
                    adj[child].add(nid)

        # Semantic edges: both directions
        for e in graph.get_semantic_edges():
            frm = TrugGraph.edge_from(e)
            to = TrugGraph.edge_to(e)
            # Skip cross-folder targets
            if ":" in frm or ":" in to:
                continue
            if frm in adj and to in adj:
                adj[frm].add(to)
                adj[to].add(frm)

        # BFS from roots
        visited: set[str] = set()
        queue: deque[str] = deque()
        for root in roots:
            if root in all_ids and root not in visited:
                visited.add(root)
                queue.append(root)

        while queue:
            curr = queue.popleft()
            for nxt in adj[curr]:
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)

        return all_ids - visited

    # AGENT claude SHALL DEFINE FUNCTION find_dead_nodes.
    @staticmethod
    def find_dead_nodes(graph: TrugGraph) -> set[str]:
        """Non-root nodes not referenced by any edge to_id or contains[].

        Collects all referenced IDs (edge targets + contains[] entries).
        Dead = node_ids() - referenced - root_nodes().
        Complexity: O(V+E).
        """
        all_ids = graph.node_ids()
        if not all_ids:
            return set()

        referenced: set[str] = set()

        # All edge to_ids
        for e in graph.get_all_edges():
            to = TrugGraph.edge_to(e)
            if to:
                referenced.add(to)

        # All contains[] entries
        for node in graph.get_all_nodes():
            for child_id in node.get("contains") or []:
                referenced.add(child_id)

        roots = set(graph.root_nodes())
        return all_ids - referenced - roots

    # AGENT claude SHALL DEFINE FUNCTION dominator_tree.
    @staticmethod
    def dominator_tree(graph: TrugGraph) -> dict[str, str | None]:
        """Immediate dominators of nodes reachable via semantic edges from roots.

        A virtual entry precedes every hierarchy root. None means the node is
        a root or has no strict dominator other than that entry; unreachable nodes
        are omitted. Iterative DFS and monotonically shrinking dominator sets
        handle joins and cycles without recursion. For V nodes and E semantic
        edges, at most (V + 1)^2 + 1 dataflow scans take O(V^3 * (V + E)) time
        in total, using O(V^2 + E) space.
        """
        all_ids = graph.node_ids()
        roots = graph.root_nodes()
        if not all_ids or not roots:
            return {}

        adj: dict[str, list[str]] = {}
        rev: dict[str, list[str]] = {}
        for e in graph.get_semantic_edges():
            frm = TrugGraph.edge_from(e)
            to = TrugGraph.edge_to(e)
            if ":" in frm or ":" in to:
                continue
            if frm in all_ids and to in all_ids:
                adj.setdefault(frm, []).append(to)
                rev.setdefault(to, []).append(frm)

        visited: set[str] = set()
        postorder: list[str] = []
        for root in roots:
            stack = [(root, False)]
            while stack:
                node, expanded = stack.pop()
                if expanded:
                    postorder.append(node)
                elif node not in visited:
                    visited.add(node)
                    stack.append((node, True))
                    stack.extend((succ, False) for succ in reversed(adj.get(node, [])))
        rpo = list(reversed(postorder))

        entry = "__entry__"
        while entry in all_ids:
            entry += "_"
        universe = visited | {entry}
        root_set = set(roots)
        dominators = {node: set(universe) for node in rpo}
        dominators[entry] = {entry}
        for root in roots:
            dominators[root] = {entry, root}

        changed = True
        while changed:
            changed = False
            for node in rpo:
                if node in root_set:
                    continue
                preds = [p for p in rev.get(node, []) if p in visited]
                common = set.intersection(*(dominators[p] for p in preds))
                updated = common | {node}
                if updated != dominators[node]:
                    dominators[node] = updated
                    changed = True

        result: dict[str, str | None] = {}
        for node in rpo:
            strict = dominators[node] - {entry, node}
            result[node] = max(strict, key=lambda p: len(dominators[p])) if strict else None
        return result

    # AGENT claude SHALL DEFINE FUNCTION impact_set.
    @staticmethod
    def impact_set(graph: TrugGraph, node_id: str) -> set[str]:
        """All other nodes reachable from node_id via semantic edges.

        Forward BFS through non-contains edges only.
        Excludes node_id itself, including when a cycle leads back to it.
        Empty set for non-existent node.
        Complexity: O(V+E) time and space.
        """
        if node_id not in graph.node_ids():
            return set()

        adj = _build_semantic_forward_adj(graph)
        visited: set[str] = set()
        queue: deque[str] = deque()

        for nxt in adj.get(node_id, []):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)

        while queue:
            curr = queue.popleft()
            for nxt in adj.get(curr, []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)

        return visited - {node_id}

    # AGENT claude SHALL DEFINE FUNCTION dependency_set.
    @staticmethod
    def dependency_set(graph: TrugGraph, node_id: str) -> set[str]:
        """All other nodes from which node_id is reachable via semantic edges.

        Reverse BFS through non-contains edges only.
        Excludes node_id itself, including when a cycle leads back to it.
        Empty set for non-existent node.
        Complexity: O(V+E) time and space.
        """
        if node_id not in graph.node_ids():
            return set()

        rev = _build_semantic_reverse_adj(graph)
        visited: set[str] = set()
        queue: deque[str] = deque()

        for prev in rev.get(node_id, []):
            if prev not in visited:
                visited.add(prev)
                queue.append(prev)

        while queue:
            curr = queue.popleft()
            for prev in rev.get(curr, []):
                if prev not in visited:
                    visited.add(prev)
                    queue.append(prev)

        return visited - {node_id}

    # AGENT claude SHALL DEFINE FUNCTION complexity.
    @staticmethod
    def complexity(graph: TrugGraph) -> TrugComplexityMetrics:
        """Graph complexity metrics.

        - cyclomatic: M = E - N + 2P (semantic edges, all nodes, connected components)
        - branching_factor: avg outgoing semantic edges per node with outgoing
        - max_depth: deepest containment path from root to leaf
        - edge_density: semantic_edge_count / node_count
        - node_count, edge_count (semantic only)
        Complexity: O(V+E).
        """
        all_ids = graph.node_ids()
        if not all_ids:
            return TrugComplexityMetrics(0, 0.0, 0, 0.0, 0, 0)

        semantic_edges = graph.get_semantic_edges()
        n_nodes = len(all_ids)
        n_edges = len(semantic_edges)

        # Connected components (undirected, semantic edges only)
        adj_undirected: dict[str, set[str]] = {nid: set() for nid in all_ids}
        for e in semantic_edges:
            frm = TrugGraph.edge_from(e)
            to = TrugGraph.edge_to(e)
            if ":" not in frm and ":" not in to:
                if frm in adj_undirected and to in adj_undirected:
                    adj_undirected[frm].add(to)
                    adj_undirected[to].add(frm)

        components = _count_components(all_ids, adj_undirected)
        cyclomatic = n_edges - n_nodes + 2 * components

        # Branching factor
        adj = _build_semantic_forward_adj(graph)
        nodes_with_outgoing = [nid for nid in all_ids if len(adj.get(nid, [])) > 0]
        if nodes_with_outgoing:
            total_outgoing = sum(len(adj.get(nid, [])) for nid in nodes_with_outgoing)
            branching_factor = total_outgoing / len(nodes_with_outgoing)
        else:
            branching_factor = 0.0

        # Max depth via hierarchy (containment)
        max_depth = _compute_max_hierarchy_depth(graph)

        # Edge density
        edge_density = n_edges / n_nodes if n_nodes > 0 else 0.0

        return TrugComplexityMetrics(
            cyclomatic=cyclomatic,
            branching_factor=round(branching_factor, 4),
            max_depth=max_depth,
            edge_density=round(edge_density, 4),
            node_count=n_nodes,
            edge_count=n_edges,
        )

    # AGENT claude SHALL DEFINE FUNCTION critical_path.
    @staticmethod
    def critical_path(graph: TrugGraph) -> list[str]:
        """Longest semantic path from a hierarchy root to a hierarchy leaf.

        Roots have null or missing parent_id; leaves have empty or missing
        contains. A root that is also a leaf is a one-node path. Among longest
        paths, return the smallest list in Python's ordering of lists of strings,
        or [] if no root-to-leaf path exists.

        Raise ValueError naming a cycle node with repr if a semantic cycle
        (including a self-loop) is reachable from any root, even if no leaf is
        reachable. Cycles no root reaches have no effect.

        Iterative DFS checks cycles and builds postorder; suffix lengths and
        next hops select the path without storing every suffix. For V nodes
        and E edges, O(V+E) graph operations and O(V+E) space, excluding the
        cost of comparing node identifier strings.
        """
        roots = graph.root_nodes()
        leaves = set(graph.leaf_nodes())
        adj = _build_semantic_forward_adj(graph)

        # Active DFS nodes form a path; an edge back to one closes a cycle.
        state: dict[str, int] = {}
        postorder: list[str] = []
        for root in roots:
            if root in state:
                continue
            state[root] = 1
            stack = [(root, iter(adj.get(root, [])))]
            while stack:
                node, successors = stack[-1]
                nxt = next(successors, None)
                if nxt is None:
                    stack.pop()
                    state[node] = 2
                    postorder.append(node)
                elif state.get(nxt) == 1:
                    raise ValueError(f"Semantic cycle reachable from a root at {nxt!r}")
                elif nxt not in state:
                    state[nxt] = 1
                    stack.append((nxt, iter(adj.get(nxt, []))))

        # A tied suffix is ordered by its first differing node, the next hop.
        length: dict[str, int] = {}
        next_hop: dict[str, str] = {}
        for node in postorder:
            length[node] = 1 if node in leaves else 0
            for nxt in adj.get(node, []):
                if not length[nxt]:
                    continue
                size = 1 + length[nxt]
                if size > length[node] or (
                    size == length[node] and nxt < next_hop[node]
                ):
                    length[node] = size
                    next_hop[node] = nxt

        starts = [root for root in roots if length[root]]
        if not starts:
            return []
        node = min(starts, key=lambda root: (-length[root], root))
        path = [node]
        while node in next_hop:
            node = next_hop[node]
            path.append(node)
        return path

    # AGENT claude SHALL DEFINE FUNCTION find_stale_propagation.
    @staticmethod
    def find_stale_propagation(graph: TrugGraph) -> dict[str, set[str]]:
        """For each stale node, find nodes transitively affected via propagation edges.

        Forward BFS from each stale node through edges with relation in
        {'uses', 'implements', 'produces', 'depends_on'}.
        Does NOT propagate via 'contains' or 'tests' edges.

        Returns: {stale_node_id: {transitively_affected_node_ids}}.
        Complexity: O(S × (V+E)) where S = stale node count.
        """
        stale_nodes = graph.get_stale_nodes()
        if not stale_nodes:
            return {}

        # Build forward adjacency from propagation edges only
        prop_adj: dict[str, list[str]] = {}
        all_ids = graph.node_ids()
        for e in graph.get_all_edges():
            rel = e.get("relation", "")
            if rel not in _STALE_PROPAGATION_RELATIONS:
                continue
            frm = TrugGraph.edge_from(e)
            to = TrugGraph.edge_to(e)
            if ":" in frm or ":" in to:
                continue
            if frm in all_ids and to in all_ids:
                prop_adj.setdefault(frm, []).append(to)

        result: dict[str, set[str]] = {}
        for stale_id in sorted(stale_nodes):
            visited: set[str] = set()
            queue: deque[str] = deque()
            for nxt in prop_adj.get(stale_id, []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
            while queue:
                curr = queue.popleft()
                for nxt in prop_adj.get(curr, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)
            result[stale_id] = visited

        return result


# ── Private helpers ──────────────────────────────────────────────────────


def _build_semantic_forward_adj(graph: TrugGraph) -> dict[str, list[str]]:
    """Forward adjacency from semantic edges only."""
    adj: dict[str, list[str]] = {}
    all_ids = graph.node_ids()
    for e in graph.get_semantic_edges():
        frm = TrugGraph.edge_from(e)
        to = TrugGraph.edge_to(e)
        if ":" in frm or ":" in to:
            continue
        if frm in all_ids and to in all_ids:
            adj.setdefault(frm, []).append(to)
    return adj


def _build_semantic_reverse_adj(graph: TrugGraph) -> dict[str, list[str]]:
    """Reverse adjacency from semantic edges only."""
    rev: dict[str, list[str]] = {}
    all_ids = graph.node_ids()
    for e in graph.get_semantic_edges():
        frm = TrugGraph.edge_from(e)
        to = TrugGraph.edge_to(e)
        if ":" in frm or ":" in to:
            continue
        if frm in all_ids and to in all_ids:
            rev.setdefault(to, []).append(frm)
    return rev


def _count_components(node_ids: set[str], adj: dict[str, set[str]]) -> int:
    """Count connected components in an undirected graph."""
    visited: set[str] = set()
    count = 0
    for nid in node_ids:
        if nid not in visited:
            count += 1
            queue: deque[str] = deque([nid])
            visited.add(nid)
            while queue:
                curr = queue.popleft()
                for nbr in adj.get(curr, set()):
                    if nbr not in visited:
                        visited.add(nbr)
                        queue.append(nbr)
    return count


def _compute_max_hierarchy_depth(graph: TrugGraph) -> int:
    """Compute max depth of the containment hierarchy."""
    roots = graph.root_nodes()
    if not roots:
        return 0

    max_depth = 0
    for root in roots:
        # BFS level-by-level through contains[]
        visited: set[str] = {root}
        current_level = [root]
        depth = 0
        while current_level:
            depth += 1
            next_level: list[str] = []
            for nid in current_level:
                for child in graph.get_children(nid):
                    if child not in visited:
                        visited.add(child)
                        next_level.append(child)
            current_level = next_level
        if depth > max_depth:
            max_depth = depth

    return max_depth
