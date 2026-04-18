"""TrugAnalyzer — structural graph analysis for any TRUG.

Provides 8 static analysis methods over TrugGraph:
  - find_unreachable_nodes: BFS from roots via hierarchy + semantic edges
  - find_dead_nodes: nodes not referenced by any edge to_id or contains[]
  - dominator_tree: iterative dataflow from hierarchy roots
  - impact_set / dependency_set: forward/reverse BFS via semantic edges
  - complexity: cyclomatic + structural metrics
  - critical_path: longest root→leaf via semantic edges
  - find_stale_propagation: transitively affected nodes from stale sources

All methods are stateless static methods. No mutation of TrugGraph.

Issue: #618
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from trugs_tools.trug_graph import TrugGraph


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
    """

    cyclomatic: int
    branching_factor: float
    max_depth: int
    edge_density: float
    node_count: int
    edge_count: int


# Relations that propagate staleness.
_STALE_PROPAGATION_RELATIONS = frozenset({
    "uses", "implements", "produces", "depends_on",
})


class TrugAnalyzer:
    """Static analysis of TrugGraph structure. All methods are stateless."""

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
            for child_id in (node.get("contains") or []):
                referenced.add(child_id)

        roots = set(graph.root_nodes())
        return all_ids - referenced - roots

    @staticmethod
    def dominator_tree(graph: TrugGraph) -> dict[str, str | None]:
        """Immediate dominator for each reachable node via semantic edges.

        Uses root_nodes() as entry points. Iterative dataflow algorithm
        (Cooper, Harvey, Kennedy 2001). Root nodes map to None.
        Complexity: O(V^2) worst case.
        """
        all_ids = graph.node_ids()
        if not all_ids:
            return {}

        roots = graph.root_nodes()
        if not roots:
            return {}

        # Build forward adjacency from semantic edges
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

        # Compute RPO via DFS from roots
        visited: set[str] = set()
        postorder: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            for succ in adj.get(node, []):
                if succ not in visited:
                    dfs(succ)
            postorder.append(node)

        for root in roots:
            if root not in visited:
                dfs(root)

        rpo = list(reversed(postorder))
        rpo_index = {node: i for i, node in enumerate(rpo)}

        root_set = set(roots)
        idom: dict[str, str | None] = {}
        for root in roots:
            if root in rpo_index:
                idom[root] = root

        def intersect(b1: str, b2: str) -> str:
            finger1, finger2 = b1, b2
            while finger1 != finger2:
                while rpo_index.get(finger1, len(rpo)) > rpo_index.get(finger2, len(rpo)):
                    parent = idom.get(finger1)
                    if parent is None:
                        break
                    finger1 = parent
                while rpo_index.get(finger2, len(rpo)) > rpo_index.get(finger1, len(rpo)):
                    parent = idom.get(finger2)
                    if parent is None:
                        break
                    finger2 = parent
            return finger1

        changed = True
        while changed:
            changed = False
            for node in rpo:
                if node in root_set:
                    continue
                preds = [p for p in rev.get(node, []) if p in idom]
                if not preds:
                    continue
                new_idom = preds[0]
                for p in preds[1:]:
                    new_idom = intersect(new_idom, p)
                if idom.get(node) != new_idom:
                    idom[node] = new_idom
                    changed = True

        result: dict[str, str | None] = {}
        for node in rpo:
            if node in root_set:
                result[node] = None
            else:
                result[node] = idom.get(node)

        return result

    @staticmethod
    def impact_set(graph: TrugGraph, node_id: str) -> set[str]:
        """All nodes transitively downstream of node_id via semantic edges.

        Forward BFS through non-contains edges only.
        Excludes node_id itself. Empty set for non-existent node.
        Complexity: O(V+E).
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

        return visited

    @staticmethod
    def dependency_set(graph: TrugGraph, node_id: str) -> set[str]:
        """All nodes transitively upstream of node_id via semantic edges.

        Reverse BFS through non-contains edges only.
        Excludes node_id itself. Empty set for non-existent node.
        Complexity: O(V+E).
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

        return visited

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

    @staticmethod
    def critical_path(graph: TrugGraph) -> list[str]:
        """Longest path from any root to any leaf via semantic edges.

        Topological traversal, track max distance + predecessor.
        Returns ordered list of node IDs. Empty if no roots or leaves.
        Complexity: O(V+E).
        """
        roots = graph.root_nodes()
        leaves = set(graph.leaf_nodes())
        if not roots or not leaves:
            return []

        adj = _build_semantic_forward_adj(graph)
        all_ids = graph.node_ids()

        # Topological order via Kahn's algorithm on semantic edges
        in_degree: dict[str, int] = {nid: 0 for nid in all_ids}
        for e in graph.get_semantic_edges():
            to = TrugGraph.edge_to(e)
            if ":" not in to and to in in_degree:
                in_degree[to] += 1

        topo_queue: deque[str] = deque()
        for nid in all_ids:
            if in_degree[nid] == 0:
                topo_queue.append(nid)

        topo_order: list[str] = []
        while topo_queue:
            curr = topo_queue.popleft()
            topo_order.append(curr)
            for nxt in adj.get(curr, []):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    topo_queue.append(nxt)

        # Longest path from roots
        dist: dict[str, int] = {}
        pred: dict[str, str | None] = {}

        for root in roots:
            if root in all_ids:
                dist[root] = 1
                pred[root] = None

        for node in topo_order:
            if node not in dist:
                continue
            for nxt in adj.get(node, []):
                new_dist = dist[node] + 1
                if new_dist > dist.get(nxt, 0):
                    dist[nxt] = new_dist
                    pred[nxt] = node

        # Find leaf with max distance
        best_leaf = None
        best_dist = 0
        for leaf in leaves:
            if leaf in dist and dist[leaf] > best_dist:
                best_dist = dist[leaf]
                best_leaf = leaf

        if best_leaf is None:
            # No leaf reachable from roots via semantic edges — try single root+leaf node
            for root in roots:
                if root in leaves:
                    return [root]
            return []

        # Backtrack
        path: list[str] = []
        curr: str | None = best_leaf
        while curr is not None:
            path.append(curr)
            curr = pred.get(curr)
        path.reverse()
        return path

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
