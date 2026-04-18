"""TrugGraph — domain-agnostic graph model for any TRUG.

Extends BaseGraph with hierarchy-aware accessors for roots, leaves,
ancestors, descendants, and edge traversal. Works on any TRUG regardless
of branch vocabulary.

Issue: #618
"""

from __future__ import annotations

from collections import deque

from trugs_store import BaseGraph
from trugs_store.memory import InMemoryGraphStore


# AGENT claude SHALL DEFINE RECORD truggraph AS RECORD class.
class TrugGraph(BaseGraph):
    """Domain-agnostic graph model built on BaseGraph.

    Provides hierarchy-aware accessors (root_nodes, leaf_nodes, ancestors,
    descendants) and edge classification (semantic vs. contains) that work
    on any TRUG — folder TRUGs, compute TRUGs, project TRUGs, etc.
    """

    # ── Hierarchy accessors ──────────────────────────────────────────────

    # AGENT claude SHALL DEFINE FUNCTION root_nodes.
    def root_nodes(self) -> list[str]:
        """Nodes where parent_id is None, null, or missing.

        In a well-formed TRUG, there is typically one root (the FOLDER node).
        """
        roots: list[str] = []
        for node in self._store._nodes.values():
            parent = node.get("parent_id")
            if parent is None:
                roots.append(node["id"])
        return roots

    # AGENT claude SHALL DEFINE FUNCTION leaf_nodes.
    def leaf_nodes(self) -> list[str]:
        """Nodes where contains is [] or missing."""
        leaves: list[str] = []
        for node in self._store._nodes.values():
            contains = node.get("contains")
            if not contains:  # None, missing, or empty list
                leaves.append(node["id"])
        return leaves

    # AGENT claude SHALL DEFINE FUNCTION get_children.
    def get_children(self, node_id: str) -> list[str]:
        """Get IDs of direct children from node's contains[] array."""
        node = self._store.get_node(node_id)
        if node is None:
            return []
        return list(node.get("contains") or [])

    # AGENT claude SHALL DEFINE FUNCTION get_parent.
    def get_parent(self, node_id: str) -> str | None:
        """Get parent_id of a node."""
        node = self._store.get_node(node_id)
        if node is None:
            return None
        return node.get("parent_id")

    # AGENT claude SHALL DEFINE FUNCTION get_ancestors.
    def get_ancestors(self, node_id: str) -> list[str]:
        """Walk parent_id chain upward to root. Ordered [parent, grandparent, ...].

        Stops at root (parent_id == None). Uses visited set to prevent
        infinite loops on malformed data.
        """
        ancestors: list[str] = []
        visited: set[str] = {node_id}
        current = node_id

        while True:
            parent = self.get_parent(current)
            if parent is None or parent in visited:
                break
            ancestors.append(parent)
            visited.add(parent)
            current = parent

        return ancestors

    # AGENT claude SHALL DEFINE FUNCTION get_descendants.
    def get_descendants(self, node_id: str) -> set[str]:
        """BFS through contains[] downward. Excludes node_id itself."""
        descendants: set[str] = set()
        queue: deque[str] = deque()

        for child in self.get_children(node_id):
            if child not in descendants:
                descendants.add(child)
                queue.append(child)

        while queue:
            curr = queue.popleft()
            for child in self.get_children(curr):
                if child not in descendants:
                    descendants.add(child)
                    queue.append(child)

        return descendants

    # ── Edge accessors ───────────────────────────────────────────────────

    # AGENT claude SHALL DEFINE FUNCTION get_edges_by_relation.
    def get_edges_by_relation(self, relation: str) -> list[dict]:
        """Get all edges with a specific relation type."""
        return self._store.get_edges(relation=relation)

    # AGENT claude SHALL DEFINE FUNCTION get_outgoing.
    def get_outgoing(self, node_id: str) -> list[dict]:
        """Get all outgoing edges from a node."""
        return self._store.get_outgoing(node_id)

    # AGENT claude SHALL DEFINE FUNCTION get_incoming.
    def get_incoming(self, node_id: str) -> list[dict]:
        """Get all incoming edges to a node."""
        return self._store.get_incoming(node_id)

    # AGENT claude SHALL DEFINE FUNCTION get_semantic_edges.
    def get_semantic_edges(self) -> list[dict]:
        """All edges where relation != 'contains'.

        These are the structurally meaningful edges for analysis:
        uses, implements, tests, describes, governs, FEEDS, ROUTES, etc.
        """
        return [e for e in self._store._edges if e.get("relation") != "contains"]

    # ── Stale accessors ──────────────────────────────────────────────────

    # AGENT claude SHALL DEFINE FUNCTION get_stale_nodes.
    def get_stale_nodes(self) -> list[str]:
        """Nodes where properties.stale == True."""
        stale: list[str] = []
        for node in self._store._nodes.values():
            props = node.get("properties", {})
            if props.get("stale") is True:
                stale.append(node["id"])
        return stale

    # AGENT claude SHALL DEFINE FUNCTION is_stale.
    def is_stale(self, node_id: str) -> bool:
        """Check if a node is marked stale."""
        node = self._store.get_node(node_id)
        if node is None:
            return False
        return node.get("properties", {}).get("stale") is True

    # ── Metadata ─────────────────────────────────────────────────────────

    # AGENT claude SHALL DEFINE FUNCTION vocabularies.
    def vocabularies(self) -> list[str]:
        """Get vocabularies from capabilities."""
        caps = self._store.get_metadata().get("capabilities", {})
        return caps.get("vocabularies", [])

    # AGENT claude SHALL DEFINE FUNCTION extensions.
    def extensions(self) -> list[str]:
        """Get extensions from capabilities."""
        caps = self._store.get_metadata().get("capabilities", {})
        return caps.get("extensions", [])
