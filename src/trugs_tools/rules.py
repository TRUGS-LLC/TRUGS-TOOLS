# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Implementation of the 11 TRUGS v1.0 validation rules.

Provides one validator function per rule (Rules 1–11) plus a root-field
validator. Each function mutates a ValidationResult with errors or warnings.

<trl>
PROCESS rules SHALL VALIDATE RECORD trug_graph AGAINST DATA validation_rule AND EMIT RECORD validation_result.
</trl>
"""

from typing import Dict, List, Set, Any, Optional
from trugs_tools.errors import ValidationResult


# AGENT claude SHALL DEFINE FUNCTION validate_rule_1_unique_ids.
def validate_rule_1_unique_ids(trug: Dict[str, Any], result: ValidationResult) -> None:
    """Rule 1: All node IDs must be unique within the graph.

    Error Code: DUPLICATE_NODE_ID

    <trl>
    FUNCTION validate_rule_1_unique_ids SHALL SCAN RECORD trug_graph THEN EMIT RECORD validation_result WITH DATA duplicate_node_id SUBJECT_TO DATA node_id REPEAT.
    </trl>
    """
    nodes = trug.get("nodes", [])
    seen_ids: Set[str] = set()

    for i, node in enumerate(nodes):
        node_id = node.get("id")

        if not node_id:
            result.add_error(
                code="MISSING_NODE_ID",
                message="Node must have an 'id' field",
                location=f"nodes[{i}]",
            )
            continue

        if node_id in seen_ids:
            result.add_error(
                code="DUPLICATE_NODE_ID",
                message=f"Node ID '{node_id}' is not unique",
                location=f"nodes[{i}]",
                node_id=node_id,
            )

        seen_ids.add(node_id)


# AGENT claude SHALL DEFINE FUNCTION validate_rule_2_parent_contains_consistency.
def validate_rule_2_parent_contains_consistency(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Rule 2: parent_id and contains must be consistent.

    Checks TWO containment mechanisms:
    1. Node's contains[] array field (CORE spec: required on every node)
    2. 'contains' edges in the edges[] array (optional, explicit edges)

    If node A has parent_id=B, then B must list A in its contains[] array.
    If node B lists A in its contains[] array, then A must have parent_id=B.

    Error Codes: PARENT_MISSING_CONTAINS, CONTAINS_MISSING_PARENT

    <trl>
    FUNCTION validate_rule_2_parent_contains_consistency SHALL VALIDATE RECORD trug_graph THEN EMIT RECORD validation_result SUBJECT_TO DATA parent_id AND DATA contains_array MATCH BIDIRECTIONALLY.
    </trl>
    """
    nodes = trug.get("nodes", [])
    edges = trug.get("edges", [])

    # Build map of node_id -> node
    node_map = {node.get("id"): node for node in nodes if node.get("id")}

    # Build map of parent -> children from parent_id fields
    parent_to_children: Dict[str, Set[str]] = {}
    for node in nodes:
        node_id = node.get("id")
        parent_id = node.get("parent_id")

        if parent_id and node_id:
            if parent_id not in parent_to_children:
                parent_to_children[parent_id] = set()
            parent_to_children[parent_id].add(node_id)

    # Build map of parent -> children from contains[] field on nodes
    contains_from_field: Dict[str, Set[str]] = {}
    for node in nodes:
        node_id = node.get("id")
        contains_arr = node.get("contains", [])
        if node_id and contains_arr:
            contains_from_field[node_id] = set(contains_arr)

    # Also consider 'contains' edges in the edges array
    for edge in edges:
        if edge.get("relation") == "contains":
            from_id = edge.get("from_id")
            to_id = edge.get("to_id")
            if from_id and to_id:
                if from_id not in contains_from_field:
                    contains_from_field[from_id] = set()
                contains_from_field[from_id].add(to_id)

    # Check consistency: parent_id implies contains (field or edge)
    for parent_id, children in parent_to_children.items():
        for child_id in children:
            if (
                parent_id not in contains_from_field
                or child_id not in contains_from_field[parent_id]
            ):
                result.add_error(
                    code="PARENT_MISSING_CONTAINS",
                    message=f"Node '{child_id}' has parent_id='{parent_id}' but parent does not list it in contains[] and no 'contains' edge exists",
                    node_id=child_id,
                    details={"parent_id": parent_id},
                )

    # Check consistency: contains (field or edge) implies parent_id
    for parent_id, children in contains_from_field.items():
        for child_id in children:
            if child_id in node_map:
                actual_parent = node_map[child_id].get("parent_id")
                if actual_parent != parent_id:
                    result.add_error(
                        code="CONTAINS_MISSING_PARENT",
                        message=f"Node '{parent_id}' lists '{child_id}' in contains but child has parent_id='{actual_parent}'",
                        node_id=child_id,
                        details={
                            "expected_parent": parent_id,
                            "actual_parent": actual_parent,
                        },
                    )


# AGENT claude SHALL DEFINE FUNCTION validate_rule_3_no_self_containment.
def validate_rule_3_no_self_containment(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Rule 3: A node cannot contain itself (directly or transitively).

    Detects cycles in the containment hierarchy.
    Uses both contains[] field on nodes and 'contains' edges.

    Error Code: SELF_CONTAINMENT_CYCLE

    <trl>
    FUNCTION validate_rule_3_no_self_containment SHALL SCAN RECORD trug_graph FOR DATA containment_cycle THEN EMIT RECORD validation_result SUBJECT_TO DATA cycle EXIST IN DATA contains_graph.
    </trl>
    """
    nodes = trug.get("nodes", [])
    edges = trug.get("edges", [])

    # Build containment graph from both contains[] fields and edges
    contains_graph: Dict[str, List[str]] = {}

    # From node contains[] fields
    for node in nodes:
        node_id = node.get("id")
        contains_arr = node.get("contains", [])
        if node_id and contains_arr:
            contains_graph[node_id] = list(contains_arr)

    # Merge in 'contains' edges
    for edge in edges:
        if edge.get("relation") == "contains":
            from_id = edge.get("from_id")
            to_id = edge.get("to_id")
            if from_id and to_id:
                if from_id not in contains_graph:
                    contains_graph[from_id] = []
                if to_id not in contains_graph[from_id]:
                    contains_graph[from_id].append(to_id)

    # DFS to detect cycles
    # AGENT claude SHALL DEFINE FUNCTION has_cycle.
    def has_cycle(
        node_id: str, visited: Set[str], rec_stack: Set[str]
    ) -> Optional[List[str]]:
        """Return cycle path if found, None otherwise."""
        visited.add(node_id)
        rec_stack.add(node_id)

        for child_id in contains_graph.get(node_id, []):
            if child_id not in visited:
                cycle = has_cycle(child_id, visited, rec_stack)
                if cycle:
                    cycle.append(node_id)
                    return cycle
            elif child_id in rec_stack:
                # Found cycle
                return [child_id, node_id]

        rec_stack.remove(node_id)
        return None

    visited: Set[str] = set()
    for node in nodes:
        node_id = node.get("id")
        if node_id and node_id not in visited:
            cycle = has_cycle(node_id, visited, set())
            if cycle:
                cycle.reverse()
                cycle_str = " -> ".join(cycle)
                result.add_error(
                    code="SELF_CONTAINMENT_CYCLE",
                    message=f"Cycle detected in containment hierarchy: {cycle_str}",
                    node_id=cycle[0],
                    details={"cycle": cycle},
                )
                # Report only first cycle to avoid noise
                return


# AGENT claude SHALL DEFINE FUNCTION validate_rule_4_edges_array.
def validate_rule_4_edges_array(trug: Dict[str, Any], result: ValidationResult) -> None:
    """Rule 4: TRUG must have an 'edges' array.

    Error Code: MISSING_EDGES_ARRAY

    <trl>
    FUNCTION validate_rule_4_edges_array SHALL CHECK RECORD trug_graph FOR DATA edges_array THEN EMIT RECORD validation_result SUBJECT_TO DATA edges_array MISSING OR DATA edges_array NOT ARRAY.
    </trl>
    """
    if "edges" not in trug:
        result.add_error(
            code="MISSING_EDGES_ARRAY",
            message="TRUG must have an 'edges' array",
            location="root",
        )
        return

    if not isinstance(trug["edges"], list):
        result.add_error(
            code="INVALID_EDGES_TYPE",
            message="'edges' must be an array",
            location="edges",
        )


# AGENT claude SHALL DEFINE FUNCTION validate_rule_5_valid_references.
def validate_rule_5_valid_references(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Rule 5: All edge references (from_id, to_id) must point to valid nodes.

    Error Codes: INVALID_FROM_ID, INVALID_TO_ID

    <trl>
    FUNCTION validate_rule_5_valid_references SHALL VALIDATE RECORD edge THEN EMIT RECORD validation_result SUBJECT_TO DATA from_id OR DATA to_id REFERENCE DATA node_id ABSENT FROM RECORD trug_graph.
    </trl>
    """
    nodes = trug.get("nodes", [])
    edges = trug.get("edges", [])

    # Build set of valid node IDs
    valid_ids = {node.get("id") for node in nodes if node.get("id")}

    for i, edge in enumerate(edges):
        from_id = edge.get("from_id")
        to_id = edge.get("to_id")

        if not from_id:
            result.add_error(
                code="MISSING_FROM_ID",
                message="Edge must have 'from_id' field",
                location=f"edges[{i}]",
            )
        elif from_id not in valid_ids:
            result.add_error(
                code="INVALID_FROM_ID",
                message=f"Edge references non-existent node '{from_id}'",
                location=f"edges[{i}]",
                details={"from_id": from_id},
            )

        if not to_id:
            result.add_error(
                code="MISSING_TO_ID",
                message="Edge must have 'to_id' field",
                location=f"edges[{i}]",
            )
        elif ":" in to_id:
            # Cross-folder reference (folder_name:node_id) — skip local validation
            pass
        elif to_id not in valid_ids:
            result.add_error(
                code="INVALID_TO_ID",
                message=f"Edge references non-existent node '{to_id}'",
                location=f"edges[{i}]",
                details={"to_id": to_id},
            )


# AGENT claude SHALL DEFINE FUNCTION validate_rule_6_required_node_fields.
def validate_rule_6_required_node_fields(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Rule 6: Nodes must have required CORE fields.

    Required fields: id, type, metric_level

    Error Codes: MISSING_NODE_FIELD

    <trl>
    FUNCTION validate_rule_6_required_node_fields SHALL CHECK RECORD node FOR DATA id AND DATA type AND DATA metric_level THEN EMIT RECORD validation_result SUBJECT_TO ANY FIELD MISSING.
    </trl>
    """
    nodes = trug.get("nodes", [])
    required_fields = ["id", "type", "metric_level"]

    for i, node in enumerate(nodes):
        node_id = node.get("id", f"nodes[{i}]")

        for field in required_fields:
            if field not in node:
                result.add_error(
                    code="MISSING_NODE_FIELD",
                    message=f"Node missing required field '{field}'",
                    location=f"nodes[{i}]",
                    node_id=node_id,
                    details={"field": field},
                )


# AGENT claude SHALL DEFINE FUNCTION validate_rule_7_required_edge_fields.
def validate_rule_7_required_edge_fields(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Rule 7: Edges must have required CORE fields.

    Required fields: from_id, to_id, relation
    Optional field: weight (if present, must be a number in 0.0–1.0 range)

    Error Codes: MISSING_EDGE_FIELD, INVALID_EDGE_WEIGHT

    <trl>
    FUNCTION validate_rule_7_required_edge_fields SHALL CHECK RECORD edge FOR DATA from_id AND DATA to_id AND DATA relation THEN EMIT RECORD validation_result SUBJECT_TO ANY FIELD MISSING OR DATA weight OUT OF RANGE.
    </trl>
    """
    edges = trug.get("edges", [])
    required_fields = ["from_id", "to_id", "relation"]

    for i, edge in enumerate(edges):
        for field in required_fields:
            if field not in edge:
                result.add_error(
                    code="MISSING_EDGE_FIELD",
                    message=f"Edge missing required field '{field}'",
                    location=f"edges[{i}]",
                    details={"field": field},
                )

        if "weight" in edge:
            from_id = edge.get("from_id", f"edges[{i}]")
            to_id = edge.get("to_id", "?")
            weight = edge["weight"]
            if not isinstance(weight, (int, float)) or isinstance(weight, bool):
                result.add_error(
                    code="INVALID_EDGE_WEIGHT",
                    message=f"Edge {from_id} → {to_id}: weight must be a number between 0.0 and 1.0, got {weight!r}",
                    location=f"edges[{i}]",
                    details={"weight": weight},
                )
            elif weight < 0.0 or weight > 1.0:
                result.add_error(
                    code="INVALID_EDGE_WEIGHT",
                    message=f"Edge {from_id} → {to_id}: weight must be a number between 0.0 and 1.0, got {weight}",
                    location=f"edges[{i}]",
                    details={"weight": weight},
                )


# AGENT claude SHALL DEFINE FUNCTION validate_rule_8_extensions_valid.
def validate_rule_8_extensions_valid(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Rule 8: Extension fields must be valid.

    Extensions are stored in node.properties.extensions.
    Each extension name must be alphanumeric with underscores.

    Error Code: INVALID_EXTENSION

    <trl>
    FUNCTION validate_rule_8_extensions_valid SHALL VALIDATE DATA extension_name IN RECORD node THEN EMIT RECORD validation_result SUBJECT_TO DATA extension_name CONTAIN INVALID CHARACTER.
    </trl>
    """
    nodes = trug.get("nodes", [])

    for i, node in enumerate(nodes):
        node_id = node.get("id", f"nodes[{i}]")
        properties = node.get("properties", {})
        extensions = properties.get("extensions", {})

        if extensions and not isinstance(extensions, dict):
            result.add_error(
                code="INVALID_EXTENSION_TYPE",
                message="Node extensions must be a dictionary",
                location=f"nodes[{i}].properties.extensions",
                node_id=node_id,
            )
            continue

        for ext_name in extensions.keys():
            if not ext_name.replace("_", "").isalnum():
                result.add_error(
                    code="INVALID_EXTENSION",
                    message=f"Extension name '{ext_name}' contains invalid characters",
                    location=f"nodes[{i}].properties.extensions",
                    node_id=node_id,
                    details={"extension": ext_name},
                )


# AGENT claude SHALL DEFINE FUNCTION validate_rule_9_metric_level_format.
def validate_rule_9_metric_level_format(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Rule 9: metric_level must follow {SI_PREFIX}_{SEMANTIC_NAME} format.

    Valid SI prefixes per TRUGS v1.0 SCHEMA.md:
    YOTTA, ZETTA, EXA, PETA, TERA, GIGA, MEGA, KILO, HECTO, DEKA,
    BASE, DECI, CENTI, MILLI, MICRO, NANO, PICO, FEMTO, ATTO, ZEPTO, YOCTO

    Error Code: INVALID_METRIC_LEVEL

    <trl>
    FUNCTION validate_rule_9_metric_level_format SHALL VALIDATE DATA metric_level IN RECORD node THEN EMIT RECORD validation_result SUBJECT_TO DATA si_prefix NOT IN DATA valid_si_prefix_set.
    </trl>
    """
    nodes = trug.get("nodes", [])
    valid_si_prefixes = {
        "YOTTA",
        "ZETTA",
        "EXA",
        "PETA",
        "TERA",
        "GIGA",
        "MEGA",
        "KILO",
        "HECTO",
        "DEKA",
        "BASE",
        "DECI",
        "CENTI",
        "MILLI",
        "MICRO",
        "NANO",
        "PICO",
        "FEMTO",
        "ATTO",
        "ZEPTO",
        "YOCTO",
    }

    for i, node in enumerate(nodes):
        node_id = node.get("id", f"nodes[{i}]")
        metric_level = node.get("metric_level")

        if not metric_level:
            # Already caught by Rule 6
            continue

        if not isinstance(metric_level, str):
            result.add_error(
                code="INVALID_METRIC_LEVEL",
                message="metric_level must be a string",
                location=f"nodes[{i}].metric_level",
                node_id=node_id,
            )
            continue

        # Must be UPPERCASE
        if not metric_level.isupper():
            result.add_error(
                code="INVALID_METRIC_LEVEL",
                message=f"metric_level '{metric_level}' must be UPPERCASE",
                location=f"nodes[{i}].metric_level",
                node_id=node_id,
            )
            continue

        # AAA #1926 SP1 — bare-prefix (`BASE`, `KILO`) is the canonical form
        # post-migration per SC-18; legacy PREFIX_NAME (`BASE_MEMORY`,
        # `KILO_STORE`) stays valid for non-memory stores using
        # `PREFIX_STORE`-style semantics.
        prefix = metric_level.split("_", 1)[0] if "_" in metric_level else metric_level
        if prefix not in valid_si_prefixes:
            result.add_error(
                code="INVALID_METRIC_PREFIX",
                message=f"metric_level prefix '{prefix}' is not a valid SI prefix",
                location=f"nodes[{i}].metric_level",
                node_id=node_id,
                details={"valid_prefixes": sorted(valid_si_prefixes)},
            )


# AGENT claude SHALL DEFINE FUNCTION validate_required_root_fields.
def validate_required_root_fields(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Validate that TRUG has required root fields.

    Required: name, version, type, nodes, edges

    <trl>
    FUNCTION validate_required_root_fields SHALL CHECK RECORD trug_graph FOR DATA name AND DATA version AND DATA type AND DATA nodes THEN EMIT RECORD validation_result SUBJECT_TO ANY ROOT FIELD MISSING.
    </trl>
    """
    required_fields = ["name", "version", "type", "nodes"]

    for field in required_fields:
        if field not in trug:
            result.add_error(
                code="MISSING_ROOT_FIELD",
                message=f"TRUG missing required root field '{field}'",
                location="root",
                details={"field": field},
            )

    # Check types
    if "nodes" in trug and not isinstance(trug["nodes"], list):
        result.add_error(
            code="INVALID_NODES_TYPE",
            message="'nodes' must be an array",
            location="nodes",
        )


# ─── Rule 10: Unreachable Nodes ─────────────────────────────────────────────


# AGENT claude SHALL DEFINE FUNCTION validate_rule_10_unreachable_nodes.
def validate_rule_10_unreachable_nodes(
    trug: Dict[str, Any], result: ValidationResult
) -> None:
    """Rule 10: Warn about nodes not reachable from any root.

    Nodes that have no hierarchy path (via contains[]) and no semantic
    edge path from any root are structurally orphaned.

    Warning Code: UNREACHABLE_NODE

    <trl>
    FUNCTION validate_rule_10_unreachable_nodes SHALL COMPUTE DATA reachable_set FROM RECORD trug_graph THEN EMIT RECORD validation_result FOR EACH RECORD node ABSENT FROM DATA reachable_set.
    </trl>
    """
    from trugs_tools.analyzer import TrugAnalyzer
    from trugs_tools.trug_graph import TrugGraph

    try:
        graph = TrugGraph.from_dict(trug)
    except (KeyError, TypeError):
        return  # Malformed TRUG — other rules will catch the structural errors

    unreachable = TrugAnalyzer.find_unreachable_nodes(graph)

    for node_id in sorted(unreachable):
        result.add_warning(
            code="UNREACHABLE_NODE",
            message=f"Node '{node_id}' is not reachable from any root node",
            node_id=node_id,
        )


# ─── Rule 11: Dead Nodes ────────────────────────────────────────────────────


# AGENT claude SHALL DEFINE FUNCTION validate_rule_11_dead_nodes.
def validate_rule_11_dead_nodes(trug: Dict[str, Any], result: ValidationResult) -> None:
    """Rule 11: Warn about nodes not referenced by any edge or contains[].

    Non-root nodes that are not the target of any edge and not listed
    in any node's contains[] array are structurally dead.

    Warning Code: DEAD_NODE

    <trl>
    FUNCTION validate_rule_11_dead_nodes SHALL COMPUTE DATA dead_set FROM RECORD trug_graph THEN EMIT RECORD validation_result FOR EACH RECORD node IN DATA dead_set.
    </trl>
    """
    from trugs_tools.analyzer import TrugAnalyzer
    from trugs_tools.trug_graph import TrugGraph

    try:
        graph = TrugGraph.from_dict(trug)
    except (KeyError, TypeError):
        return  # Malformed TRUG — other rules will catch the structural errors

    dead = TrugAnalyzer.find_dead_nodes(graph)

    for node_id in sorted(dead):
        result.add_warning(
            code="DEAD_NODE",
            message=f"Node '{node_id}' is not referenced by any edge or contains[]",
            node_id=node_id,
        )
