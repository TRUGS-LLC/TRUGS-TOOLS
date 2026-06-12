# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""TRUGS validator — enforces all 16 CORE rules.

Rules 1-9: Structural (always enforced)
Rules 10-16: Compositional (enforced when core_v1.0.0 declared)

Usage:
    python -m trugs_llc.tools.validate <file.trug.json>
    python -m trugs_llc.tools.validate --all <directory>

<trl>
PROCESS validate SHALL VALIDATE RECORD trug_graph AGAINST ALL RECORD rule THEN RETURN RECORD validation_result.
</trl>
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ─── Primitives ────────────────────────────────────────────────────────────────
# From TRUGS_LLC/TRUGS_LANGUAGE/SPEC_vocabulary.md

ENTITY_ACTORS = {
    "TRANSFORM",
    "PARTY",
    "AGENT",
    "PRINCIPAL",
    "PROCESS",
    "SERVICE",
    "FUNCTION",
}
ENTITY_ARTIFACTS = {
    "DATA",
    "FILE",
    "RECORD",
    "MESSAGE",
    "STREAM",
    "RESOURCE",
    "INSTRUMENT",
}
ENTITY_CONTAINERS = {"PIPELINE", "STAGE", "MODULE", "NAMESPACE"}
ENTITY_BOUNDARIES = {
    "ENTRY",
    "FLOW_ENTRY",
    "EXIT",
    "FLOW_EXIT",
    "INTERFACE",
    "ENDPOINT",
    "JURISDICTION",
    "DEADLINE",
}
ENTITY_OUTCOMES = {"RESULT", "ERROR", "EXCEPTION", "REMEDY"}

ALL_ENTITIES = (
    ENTITY_ACTORS
    | ENTITY_ARTIFACTS
    | ENTITY_CONTAINERS
    | ENTITY_BOUNDARIES
    | ENTITY_OUTCOMES
)

OP_TRANSFORM = {
    "FILTER",
    "EXCLUDE",
    "MAP",
    "SORT",
    "MERGE",
    "SPLIT",
    "FLATTEN",
    "AGGREGATE",
    "GROUP",
    "RENAME",
    "BATCH",
    "DISTINCT",
    "TAKE",
    "SKIP",
}
OP_MOVE = {
    "READ",
    "WRITE",
    "SEND",
    "RECEIVE",
    "RETURN",
    "REQUEST",
    "RESPOND",
    "AUTHENTICATE",
    "DELIVER",
    "ASSIGN",
}
OP_OBLIGATE = {"VALIDATE", "ASSERT", "REQUIRE", "SHALL"}
OP_PERMIT = {"ALLOW", "APPROVE", "GRANT", "OVERRIDE", "MAY"}
OP_PROHIBIT = {"DENY", "REJECT", "SHALL_NOT", "REVOKE"}
OP_CONTROL = {
    "BRANCH",
    "MATCH",
    "RETRY",
    "TIMEOUT",
    "THROW",
    "EXISTS",
    "EXPIRE",
    "EQUALS",
    "EXCEEDS",
    "PRECEDES",
}
OP_CONTROL_COMPARISON = {"EXISTS", "EQUALS", "EXCEEDS", "PRECEDES", "EXPIRE"}
OP_BIND = {
    "DEFINE",
    "DECLARE",
    "IMPLEMENT",
    "NEST",
    "AUGMENT",
    "REPLACE",
    "CITE",
    "ADMINISTER",
    "STIPULATE",
}
OP_RESOLVE = {"CATCH", "HANDLE", "RECOVER", "CURE", "INDEMNIFY"}

ALL_OPERATIONS = (
    OP_TRANSFORM
    | OP_MOVE
    | OP_OBLIGATE
    | OP_PERMIT
    | OP_PROHIBIT
    | OP_CONTROL
    | OP_BIND
    | OP_RESOLVE
)

MODALS = {"SHALL", "SHALL_NOT", "MAY"}

MOD_TYPE = {"STRING", "INTEGER", "BOOLEAN", "ARRAY", "OBJECT"}
MOD_ACCESS = {"PUBLIC", "PRIVATE", "PROTECTED", "READONLY", "CONFIDENTIAL"}
MOD_STATE = {
    "VALID",
    "INVALID",
    "NULL",
    "EMPTY",
    "PENDING",
    "ACTIVE",
    "FAILED",
    "MUTABLE",
    "IMMUTABLE",
    "BINDING",
    "VOID",
    "ENFORCEABLE",
    "EXPIRED",
    "PRECEDENT",
}
MOD_QUANTITY = {"REQUIRED", "OPTIONAL", "UNIQUE", "MULTIPLE", "SOLE", "JOINT"}
MOD_PRIORITY = {"DEFAULT", "CRITICAL", "HIGH", "LOW", "MATERIAL", "SUBORDINATE"}

QUAL_TIMING = {
    "ASYNC",
    "SYNC",
    "SEQUENTIAL",
    "PARALLEL",
    "IMMEDIATE",
    "LAZY",
    "PROMPTLY",
    "FORTHWITH",
    "WITHIN",
}
QUAL_REPETITION = {"ONCE", "ALWAYS", "NEVER", "BOUNDED"}
QUAL_DEGREE = {"STRICTLY", "PARTIALLY", "SUBSTANTIALLY", "REASONABLY"}
QUAL_CONDITION = {"UNCONDITIONALLY", "CONDITIONALLY"}

SELECTOR_NEGATIVE = {"NO", "NONE"}

SI_PREFIXES = {
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

SI_VALUES = {
    "YOTTA": 1e24,
    "ZETTA": 1e21,
    "EXA": 1e18,
    "PETA": 1e15,
    "TERA": 1e12,
    "GIGA": 1e9,
    "MEGA": 1e6,
    "KILO": 1e3,
    "HECTO": 1e2,
    "DEKA": 1e1,
    "BASE": 1e0,
    "DECI": 1e-1,
    "CENTI": 1e-2,
    "MILLI": 1e-3,
    "MICRO": 1e-6,
    "NANO": 1e-9,
    "PICO": 1e-12,
    "FEMTO": 1e-15,
    "ATTO": 1e-18,
    "ZEPTO": 1e-21,
    "YOCTO": 1e-24,
}


# ─── Result Types ──────────────────────────────────────────────────────────────


# AGENT claude SHALL DEFINE RECORD validation_error AS A RECORD finding.
@dataclass
class ValidationError:
    """Represents a single validation finding (error or warning) on a TRUG graph.

    <trl>
    RECORD ValidationError SHALL REPRESENT DATA finding AND SHALL CONTAIN RECORD code AND RECORD message.
    </trl>
    """

    code: str
    message: str
    location: str = ""
    node_id: Optional[str] = None


# AGENT claude SHALL DEFINE RECORD validation_result AS A RECORD finding.
@dataclass
class ValidationResult:
    """Accumulates errors and warnings produced by a full validation run.

    <trl>
    RECORD ValidationResult SHALL AGGREGATE RECORD error AND RECORD warning THEN RETURN DATA valid_flag.
    </trl>
    """

    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    # AGENT claude SHALL VALIDATE RECORD result THEN RETURN RECORD valid.
    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    # AGENT claude SHALL WRITE RECORD error TO RECORD result.
    def error(
        self, code: str, message: str, location: str = "", node_id: Optional[str] = None
    ):
        self.errors.append(ValidationError(code, message, location, node_id))

    # AGENT claude SHALL WRITE RECORD warning TO RECORD result.
    def warn(
        self, code: str, message: str, location: str = "", node_id: Optional[str] = None
    ):
        self.warnings.append(ValidationError(code, message, location, node_id))

    # AGENT claude SHALL MAP RECORD result TO STRING DATA output.
    def summary(self) -> str:
        if self.valid and not self.warnings:
            return "VALID"
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} errors")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warnings")
        return ", ".join(parts)


# ─── Helpers ───────────────────────────────────────────────────────────────────


def _entity_class(node_type: str) -> Optional[str]:
    if node_type in ENTITY_ACTORS:
        return "Actor"
    if node_type in ENTITY_ARTIFACTS:
        return "Artifact"
    if node_type in ENTITY_CONTAINERS:
        return "Container"
    if node_type in ENTITY_BOUNDARIES:
        return "Boundary"
    if node_type in ENTITY_OUTCOMES:
        return "Outcome"
    return None


def _op_class(operation: str) -> Optional[str]:
    if operation in OP_TRANSFORM:
        return "Transform"
    if operation in OP_MOVE:
        return "Move"
    if operation in OP_OBLIGATE:
        return "Obligate"
    if operation in OP_PERMIT:
        return "Permit"
    if operation in OP_PROHIBIT:
        return "Prohibit"
    if operation in OP_CONTROL:
        return "Control"
    if operation in OP_BIND:
        return "Bind"
    if operation in OP_RESOLVE:
        return "Resolve"
    return None


def _has_core_v091(trug: Dict[str, Any]) -> bool:
    caps = trug.get("capabilities", {})
    if not isinstance(caps, dict):
        return False
    vocabs = caps.get("vocabularies", [])
    return "core_v1.0.0" in vocabs


# ─── Rules 1-9: Structural ────────────────────────────────────────────────────


# PROCESS validator SHALL REQUIRE EACH RECORD node CONTAINS UNIQUE RECORD id.
def rule_1_unique_ids(trug: Dict[str, Any], r: ValidationResult):
    """Check that every node id is present and unique across the graph.

    <trl>
    FUNCTION rule_1_unique_ids SHALL SCAN RECORD node AND SHALL REJECT RECORD id SUBJECT_TO RECORD id EQUALS RECORD duplicate.
    </trl>
    """
    seen: Set[str] = set()
    for i, node in enumerate(trug.get("nodes", [])):
        nid = node.get("id")
        if not nid:
            r.error("MISSING_NODE_ID", f"nodes[{i}] missing 'id'", f"nodes[{i}]")
        elif nid in seen:
            r.error(
                "DUPLICATE_NODE_ID", f"Duplicate node ID '{nid}'", f"nodes[{i}]", nid
            )
        else:
            seen.add(nid)


# PROCESS validator SHALL ASSERT EACH RECORD edge REFERENCES VALID RECORD node.
def rule_2_edge_id_validity(trug: Dict[str, Any], r: ValidationResult):
    """Check that every edge from_id and to_id references an existing node id.

    <trl>
    FUNCTION rule_2_edge_id_validity SHALL VALIDATE RECORD edge AND SHALL REJECT RECORD edge SUBJECT_TO RECORD from_id OR RECORD to_id EQUALS RECORD missing_node.
    </trl>
    """
    node_ids = {n.get("id") for n in trug.get("nodes", []) if n.get("id")}
    for i, edge in enumerate(trug.get("edges", [])):
        fid = edge.get("from_id")
        tid = edge.get("to_id")
        if fid and fid not in node_ids:
            r.error(
                "INVALID_EDGE_REFERENCE",
                f"Edge from_id '{fid}' not found",
                f"edges[{i}]",
            )
        if tid and ":" not in str(tid) and tid not in node_ids:
            r.error(
                "INVALID_EDGE_REFERENCE", f"Edge to_id '{tid}' not found", f"edges[{i}]"
            )


# PROCESS validator SHALL ASSERT RECORD parent_id AND RECORD contains MATCH EACH RECORD node.
def rule_3_hierarchy_consistency(trug: Dict[str, Any], r: ValidationResult):
    """Verify that parent_id and contains[] are mutually consistent for every node.

    <trl>
    FUNCTION rule_3_hierarchy_consistency SHALL VALIDATE RECORD parent_id AND RECORD contains AND SHALL REJECT RECORD node SUBJECT_TO RECORD parent_id EQUALS RECORD mismatch.
    </trl>
    """
    node_map = {n.get("id"): n for n in trug.get("nodes", []) if n.get("id")}
    for nid, node in node_map.items():
        pid = node.get("parent_id")
        if pid and pid in node_map:
            parent = node_map[pid]
            if nid not in parent.get("contains", []):
                r.error(
                    "INCONSISTENT_HIERARCHY",
                    f"'{nid}' has parent_id='{pid}' but parent's contains[] missing it",
                    node_id=nid,
                )
        for cid in node.get("contains", []):
            if cid in node_map:
                child = node_map[cid]
                if child.get("parent_id") != nid:
                    r.error(
                        "INCONSISTENT_HIERARCHY",
                        f"'{nid}' lists '{cid}' in contains[] but child's parent_id='{child.get('parent_id')}'",
                        node_id=nid,
                    )


# PROCESS validator SHALL VALIDATE RECORD parent SUBJECT_TO RECORD child THEN ASSERT RECORD metric_level.
def rule_4_metric_level_ordering(trug: Dict[str, Any], r: ValidationResult):
    """Ensure a parent node's metric_level SI prefix is never smaller than its child's.

    <trl>
    FUNCTION rule_4_metric_level_ordering SHALL VALIDATE RECORD metric_level AND SHALL REJECT RECORD node SUBJECT_TO RECORD parent_prefix EXCEEDS RECORD child_prefix.
    </trl>
    """
    node_map = {n.get("id"): n for n in trug.get("nodes", []) if n.get("id")}
    for nid, node in node_map.items():
        pid = node.get("parent_id")
        if not pid or pid not in node_map:
            continue
        parent = node_map[pid]
        p_ml = parent.get("metric_level", "")
        c_ml = node.get("metric_level", "")
        p_prefix = p_ml.split("_")[0] if "_" in p_ml else ""
        c_prefix = c_ml.split("_")[0] if "_" in c_ml else ""
        if p_prefix in SI_VALUES and c_prefix in SI_VALUES:
            if SI_VALUES[p_prefix] < SI_VALUES[c_prefix]:
                r.error(
                    "INVALID_METRIC_ORDERING",
                    f"Parent '{pid}' ({p_ml}) < child '{nid}' ({c_ml})",
                    node_id=nid,
                )


# PROCESS validator SHALL REQUIRE EACH RECORD dimension SUBJECT_TO RECORD dimensions.
def rule_5_dimension_declaration(trug: Dict[str, Any], r: ValidationResult):
    """Ensure every dimension referenced by a node is declared in the root dimensions map.

    <trl>
    FUNCTION rule_5_dimension_declaration SHALL VALIDATE RECORD dimension AND SHALL REJECT RECORD node SUBJECT_TO RECORD dimension EQUALS RECORD undeclared.
    </trl>
    """
    dims = trug.get("dimensions", {})
    if not isinstance(dims, dict):
        return  # Malformed dimensions — rule_7 will catch the type error
    declared = set(dims.keys())
    for i, node in enumerate(trug.get("nodes", [])):
        dim = node.get("dimension")
        if dim and dim not in declared:
            r.error(
                "UNDECLARED_DIMENSION",
                f"Node '{node.get('id')}' uses undeclared dimension '{dim}'",
                node_id=node.get("id"),
            )


# PROCESS validator SHALL ASSERT EACH RECORD node AND RECORD edge CONTAINS REQUIRED RECORD field.
def rule_6_required_fields(trug: Dict[str, Any], r: ValidationResult):
    """Assert that every node and edge contains all 7 / 3 required fields respectively.

    <trl>
    FUNCTION rule_6_required_fields SHALL VALIDATE RECORD node AND RECORD edge AND SHALL REJECT RECORD entity SUBJECT_TO RECORD required_field EQUALS RECORD missing.
    </trl>
    """
    # Root fields checked separately in validate() for early return
    node_fields = [
        "id",
        "type",
        "properties",
        "parent_id",
        "contains",
        "metric_level",
        "dimension",
    ]
    for i, node in enumerate(trug.get("nodes", [])):
        for f in node_fields:
            if f not in node:
                r.error(
                    "MISSING_REQUIRED_FIELD",
                    f"Node '{node.get('id', i)}' missing field '{f}'",
                    f"nodes[{i}]",
                    node.get("id"),
                )
    edge_fields = ["from_id", "to_id", "relation"]
    for i, edge in enumerate(trug.get("edges", [])):
        for f in edge_fields:
            if f not in edge:
                r.error(
                    "MISSING_REQUIRED_FIELD",
                    f"Edge [{i}] missing field '{f}'",
                    f"edges[{i}]",
                )


# PROCESS validator SHALL ASSERT EACH RECORD field THEN MATCH REQUIRED DATA type.
def rule_7_field_type_correctness(trug: Dict[str, Any], r: ValidationResult):
    """Check that node and edge fields carry the correct JSON types (string, list, dict, number).

    <trl>
    FUNCTION rule_7_field_type_correctness SHALL VALIDATE DATA type AND SHALL REJECT RECORD field SUBJECT_TO DATA type EQUALS RECORD mismatch.
    </trl>
    """
    for i, node in enumerate(trug.get("nodes", [])):
        nid = node.get("id", f"nodes[{i}]")
        if "id" in node and not isinstance(node["id"], str):
            r.error(
                "INVALID_FIELD_TYPE", f"Node '{nid}': id must be string", node_id=nid
            )
        if "type" in node and not isinstance(node["type"], str):
            r.error(
                "INVALID_FIELD_TYPE", f"Node '{nid}': type must be string", node_id=nid
            )
        if "properties" in node and not isinstance(node["properties"], dict):
            r.error(
                "INVALID_FIELD_TYPE",
                f"Node '{nid}': properties must be object",
                node_id=nid,
            )
        if (
            "parent_id" in node
            and node["parent_id"] is not None
            and not isinstance(node["parent_id"], str)
        ):
            r.error(
                "INVALID_FIELD_TYPE",
                f"Node '{nid}': parent_id must be string or null",
                node_id=nid,
            )
        if "contains" in node and not isinstance(node["contains"], list):
            r.error(
                "INVALID_FIELD_TYPE",
                f"Node '{nid}': contains must be array",
                node_id=nid,
            )
        if "metric_level" in node and not isinstance(node["metric_level"], str):
            r.error(
                "INVALID_FIELD_TYPE",
                f"Node '{nid}': metric_level must be string",
                node_id=nid,
            )
    for i, edge in enumerate(trug.get("edges", [])):
        for f in ["from_id", "to_id", "relation"]:
            if f in edge and not isinstance(edge[f], str):
                r.error(
                    "INVALID_FIELD_TYPE",
                    f"Edge [{i}]: {f} must be string",
                    f"edges[{i}]",
                )
        if "weight" in edge:
            w = edge["weight"]
            if not isinstance(w, (int, float)) or isinstance(w, bool):
                r.error(
                    "INVALID_EDGE_WEIGHT",
                    f"Edge [{i}]: weight must be number 0.0-1.0",
                    f"edges[{i}]",
                )
            elif w < 0.0 or w > 1.0:
                r.error(
                    "INVALID_EDGE_WEIGHT",
                    f"Edge [{i}]: weight {w} outside 0.0-1.0",
                    f"edges[{i}]",
                )


# PROCESS validator SHALL REQUIRE EACH RECORD extension SUBJECT_TO RECORD capabilities.
def rule_8_extension_declaration(trug: Dict[str, Any], r: ValidationResult):
    """Ensure any extension property used by a node is declared in capabilities.extensions.

    <trl>
    FUNCTION rule_8_extension_declaration SHALL VALIDATE RECORD extension AND SHALL REJECT RECORD node SUBJECT_TO RECORD extension EQUALS RECORD undeclared.
    </trl>
    """
    capabilities = trug.get("capabilities", {})
    if not isinstance(capabilities, dict):
        r.error(
            "INVALID_FIELD_TYPE",
            f"Root field 'capabilities' must be object, got {type(capabilities).__name__}",
            "capabilities",
        )
        return
    declared_ext = set(capabilities.get("extensions", []))
    for i, node in enumerate(trug.get("nodes", [])):
        props = node.get("properties", {})
        if "type_info" in props and "typed" not in declared_ext:
            r.error(
                "UNDECLARED_EXTENSION",
                f"Node '{node.get('id')}' uses typed extension but it's not declared",
                node_id=node.get("id"),
            )


# PROCESS validator SHALL ASSERT EACH RECORD metric_level THEN MATCH RECORD format.
def rule_9_metric_level_format(trug: Dict[str, Any], r: ValidationResult):
    """Validate that each metric_level starts with a recognized SI prefix.

    <trl>
    FUNCTION rule_9_metric_level_format SHALL VALIDATE RECORD metric_level AND SHALL REJECT RECORD node SUBJECT_TO RECORD si_prefix EQUALS RECORD invalid.
    </trl>
    """
    # AAA #1926 SP1 — accept both canonical bare-prefix (`BASE`, `KILO`) and
    # legacy PREFIX_NAME (`BASE_MEMORY`, `KILO_STORE`) forms. The bare-prefix
    # form is the post-migration target per SC-18; the underscored form stays
    # valid for non-memory stores that use `PREFIX_STORE`-style semantics.
    for i, node in enumerate(trug.get("nodes", [])):
        ml = node.get("metric_level")
        if not ml or not isinstance(ml, str):
            continue
        prefix = ml.split("_", 1)[0] if "_" in ml else ml
        if prefix not in SI_PREFIXES:
            r.error(
                "INVALID_METRIC_FORMAT",
                f"Invalid SI prefix '{prefix}' in '{ml}'",
                node_id=node.get("id"),
            )


# ─── Rules 10-16: Compositional (opt-in via core_v1.0.0) ──────────────────────


# PROCESS validator SHALL ASSERT EACH RECORD subject THEN MATCH RECORD operation BY RECORD entity.
def rule_10_subject_operation(trug: Dict[str, Any], r: ValidationResult):
    """Subject-Operation compatibility.

    <trl>
    FUNCTION rule_10_subject_operation SHALL VALIDATE RECORD subject AND SHALL REJECT RECORD edge SUBJECT_TO RECORD entity_class EQUALS RECORD incompatible_operation.
    </trl>
    """
    node_map = {n.get("id"): n for n in trug.get("nodes", []) if n.get("id")}
    for edge in trug.get("edges", []):
        rel = edge.get("relation", "")
        if rel not in MODALS and rel not in ALL_OPERATIONS:
            continue
        fid = edge.get("from_id")
        if fid not in node_map:
            continue
        subject_type = node_map[fid].get("type", "")
        ec = _entity_class(subject_type)
        if not ec:
            continue
        op = rel if rel in ALL_OPERATIONS else None
        if not op:
            continue
        oc = _op_class(op)
        if ec == "Actor":
            continue  # Actors can do anything
        if ec == "Container" and oc in ("Transform", "Control", "Bind"):
            continue
        if ec == "Artifact" and oc == "Control" and op in OP_CONTROL_COMPARISON:
            continue
        if ec == "Boundary" and oc == "Bind":
            continue
        r.error(
            "INCOMPATIBLE_SUBJECT_OPERATION",
            f"'{subject_type}' ({ec}) cannot perform '{op}' ({oc})",
            node_id=fid,
        )


# PROCESS validator SHALL ASSERT EACH RECORD operation THEN MATCH RECORD object BY RECORD entity.
def rule_11_operation_object(trug: Dict[str, Any], r: ValidationResult):
    """Operation-Object compatibility.

    <trl>
    FUNCTION rule_11_operation_object SHALL VALIDATE RECORD object AND SHALL REJECT RECORD edge SUBJECT_TO RECORD object_class EQUALS RECORD incompatible_operation.
    </trl>
    """
    node_map = {n.get("id"): n for n in trug.get("nodes", []) if n.get("id")}
    for edge in trug.get("edges", []):
        rel = edge.get("relation", "")
        if rel not in ALL_OPERATIONS:
            continue
        tid = edge.get("to_id")
        if tid not in node_map:
            continue
        obj_type = node_map[tid].get("type", "")
        ec = _entity_class(obj_type)
        if not ec:
            continue
        oc = _op_class(rel)
        if ec == "Artifact" and oc in (
            "Transform",
            "Move",
            "Obligate",
            "Control",
            "Bind",
        ):
            continue
        if ec == "Actor" and oc in ("Permit", "Prohibit"):
            continue
        if ec == "Container" and oc in ("Move", "Bind"):
            continue
        if ec == "Boundary" and oc == "Bind":
            continue
        if ec == "Outcome" and oc == "Resolve":
            continue
        r.error(
            "INCOMPATIBLE_OPERATION_OBJECT",
            f"'{obj_type}' ({ec}) cannot be target of '{rel}' ({oc})",
            node_id=tid,
        )


# PROCESS validator SHALL ASSERT EACH RECORD node THEN MATCH RECORD modifier SUBJECT_TO RECORD entity.
def rule_12_modifier_entity(trug: Dict[str, Any], r: ValidationResult):
    """Modifier-Entity compatibility.

    <trl>
    FUNCTION rule_12_modifier_entity SHALL VALIDATE RECORD modifier AND SHALL REJECT RECORD node SUBJECT_TO RECORD modifier EQUALS RECORD incompatible_entity_class.
    </trl>
    """
    for node in trug.get("nodes", []):
        nid = node.get("id", "?")
        ntype = node.get("type", "")
        ec = _entity_class(ntype)
        if not ec:
            continue
        props = node.get("properties", {})
        for key, val in props.items():
            if not isinstance(val, str):
                continue
            v = val.upper()
            if v in MOD_TYPE and ec not in ("Artifact", "Outcome"):
                r.error(
                    "INCOMPATIBLE_MODIFIER_ENTITY",
                    f"Type modifier '{val}' on {ec} '{nid}'",
                    node_id=nid,
                )
            if v in MOD_ACCESS and ec in ("Actor", "Outcome"):
                r.error(
                    "INCOMPATIBLE_MODIFIER_ENTITY",
                    f"Access modifier '{val}' on {ec} '{nid}'",
                    node_id=nid,
                )
            if v in MOD_QUANTITY and ec == "Boundary":
                r.error(
                    "INCOMPATIBLE_MODIFIER_ENTITY",
                    f"Quantity modifier '{val}' on {ec} '{nid}'",
                    node_id=nid,
                )


# PROCESS validator SHALL ASSERT EACH RECORD qualifier THEN MATCH RECORD operation SUBJECT_TO RECORD category.
def rule_13_qualifier_operation(trug: Dict[str, Any], r: ValidationResult):
    """Qualifier-Operation compatibility.

    <trl>
    FUNCTION rule_13_qualifier_operation SHALL VALIDATE RECORD qualifier AND SHALL REJECT RECORD node SUBJECT_TO RECORD qualifier EQUALS RECORD incompatible_operation_class.
    </trl>
    """
    for node in trug.get("nodes", []):
        ntype = node.get("type", "")
        if ntype != "TRANSFORM":
            continue
        nid = node.get("id", "?")
        props = node.get("properties", {})
        op = props.get("operation", "")
        oc = _op_class(op)
        if not oc:
            continue
        for key, val in props.items():
            if not isinstance(val, str):
                continue
            v = val.upper()
            if v in QUAL_TIMING and oc == "Bind":
                r.error(
                    "INCOMPATIBLE_QUALIFIER_OPERATION",
                    f"Timing qualifier '{val}' on Bind operation '{op}' in '{nid}'",
                    node_id=nid,
                )
            if v in QUAL_REPETITION and oc == "Bind":
                r.error(
                    "INCOMPATIBLE_QUALIFIER_OPERATION",
                    f"Repetition qualifier '{val}' on Bind operation '{op}' in '{nid}'",
                    node_id=nid,
                )
            if v in QUAL_DEGREE and oc in ("Transform", "Move", "Control", "Resolve"):
                r.error(
                    "INCOMPATIBLE_QUALIFIER_OPERATION",
                    f"Degree qualifier '{val}' on {oc} operation '{op}' in '{nid}'",
                    node_id=nid,
                )


# PROCESS validator SHALL ASSERT EACH RECORD modal SUBJECT_TO RECORD subject AS RECORD actor.
def rule_14_constraint_subject(trug: Dict[str, Any], r: ValidationResult):
    """Modals (SHALL, SHALL_NOT, MAY) require Actor subjects.

    <trl>
    FUNCTION rule_14_constraint_subject SHALL VALIDATE RECORD modal AND SHALL REJECT RECORD edge SUBJECT_TO RECORD subject EQUALS RECORD non_actor.
    </trl>
    """
    node_map = {n.get("id"): n for n in trug.get("nodes", []) if n.get("id")}
    for edge in trug.get("edges", []):
        rel = edge.get("relation", "")
        if rel not in MODALS:
            continue
        fid = edge.get("from_id")
        if fid not in node_map:
            continue
        subject_type = node_map[fid].get("type", "")
        if subject_type not in ENTITY_ACTORS:
            r.error(
                "CONSTRAINT_REQUIRES_ACTOR",
                f"Modal '{rel}' on non-Actor '{subject_type}' node '{fid}'",
                node_id=fid,
            )


# PROCESS validator SHALL REJECT RECORD selector SUBJECT_TO RECORD modal.
def rule_15_no_double_negation(trug: Dict[str, Any], r: ValidationResult):
    """Negative selector + Prohibit modal = double negation.

    <trl>
    FUNCTION rule_15_no_double_negation SHALL REJECT RECORD node SUBJECT_TO RECORD selector EQUALS RECORD negative AND RECORD modal EQUALS SHALL_NOT.
    </trl>
    """
    node_map = {n.get("id"): n for n in trug.get("nodes", []) if n.get("id")}
    for edge in trug.get("edges", []):
        if edge.get("relation") != "SHALL_NOT":
            continue
        fid = edge.get("from_id")
        if fid not in node_map:
            continue
        props = node_map[fid].get("properties", {})
        scope = props.get("scope", {})
        quantifier = scope.get("quantifier", "") if isinstance(scope, dict) else ""
        if quantifier.upper() in SELECTOR_NEGATIVE:
            r.error(
                "DOUBLE_NEGATION",
                f"Double negation: '{quantifier}' + SHALL_NOT on '{fid}'",
                node_id=fid,
            )


# PROCESS validator SHALL ASSERT EACH RECORD reference SUBJECT_TO RECORD graph.
def rule_16_reference_scope(trug: Dict[str, Any], r: ValidationResult):
    """References (SELF, RESULT, etc.) must resolve within subgraph scope.

    <trl>
    FUNCTION rule_16_reference_scope SHALL VALIDATE RECORD reference AND SHALL REJECT RECORD edge SUBJECT_TO RECORD to_id EQUALS RECORD unresolved.
    </trl>
    """
    references = {"SELF", "RESULT", "OUTPUT", "INPUT", "SOURCE", "TARGET", "SAID"}
    node_ids = {n.get("id") for n in trug.get("nodes", []) if n.get("id")}
    for edge in trug.get("edges", []):
        if edge.get("relation") != "REFERENCES":
            continue
        tid = edge.get("to_id", "")
        if tid.upper() in references and tid not in node_ids:
            r.error(
                "UNRESOLVED_REFERENCE",
                f"Reference '{tid}' does not resolve to a node",
                f"edge to '{tid}'",
            )


# ─── Main Validator ────────────────────────────────────────────────────────────


# PROCESS validator SHALL VALIDATE RECORD graph THEN RETURN RECORD result.
def validate(trug: Dict[str, Any]) -> ValidationResult:
    """Validate a TRUG against all applicable CORE rules.

    <trl>
    FUNCTION validate SHALL VALIDATE RECORD trug_graph AGAINST ALL RECORD rule THEN RETURN RECORD validation_result.
    </trl>
    """
    r = ValidationResult()

    if not isinstance(trug, dict):
        r.error("INVALID_ROOT", "TRUG must be a JSON object")
        return r

    # Check root structure first — can't proceed without nodes/edges
    for root_field in ["name", "version", "type", "nodes", "edges"]:
        if root_field not in trug:
            r.error(
                "MISSING_REQUIRED_FIELD", f"Missing root field '{root_field}'", "root"
            )
    if not r.valid:
        return r

    # Rules 1-9: always enforced
    rule_6_required_fields(trug, r)

    rule_1_unique_ids(trug, r)
    rule_2_edge_id_validity(trug, r)
    rule_3_hierarchy_consistency(trug, r)
    rule_4_metric_level_ordering(trug, r)
    rule_5_dimension_declaration(trug, r)
    rule_7_field_type_correctness(trug, r)
    rule_8_extension_declaration(trug, r)
    rule_9_metric_level_format(trug, r)

    # Rules 10-16: only when core_v1.0.0 declared
    if _has_core_v091(trug):
        rule_10_subject_operation(trug, r)
        rule_11_operation_object(trug, r)
        rule_12_modifier_entity(trug, r)
        rule_13_qualifier_operation(trug, r)
        rule_14_constraint_subject(trug, r)
        rule_15_no_double_negation(trug, r)
        rule_16_reference_scope(trug, r)

    return r


# PROCESS validator SHALL READ FILE path THEN VALIDATE RESULT.
def validate_file(path: Path) -> ValidationResult:
    """Load and validate a .trug.json file.

    <trl>
    FUNCTION validate_file SHALL READ FILE path THEN VALIDATE RECORD trug_graph THEN RETURN RECORD validation_result.
    </trl>
    """
    r = ValidationResult()
    try:
        with open(path, "r", encoding="utf-8") as f:
            trug = json.load(f)
    except json.JSONDecodeError as e:
        r.error("PARSE_ERROR", f"Invalid JSON: {e}", str(path))
        return r
    except FileNotFoundError:
        r.error("FILE_NOT_FOUND", f"File not found: {path}", str(path))
        return r
    return validate(trug)


# ─── CLI ───────────────────────────────────────────────────────────────────────


_HELP = """\
usage: trug validate <file.trug.json> | --all [dir]

Validate a TRUG JSON file against the 12 structural rules. With --all,
validate every *.json / *.trug.json under a directory.

examples:
  trug validate first.trug.json
  trug validate --all ./graphs

exit codes:
  0  VALID (all files pass)
  1  INVALID, file error, or no files found"""


# AGENT claude SHALL READ DATA argv THEN RETURN INTEGER DATA exit_code.
def main():
    """CLI entry point: validate one file or all files in a directory.

    <trl>
    FUNCTION main SHALL READ DATA argv THEN VALIDATE FILE path THEN RETURN DATA exit_code.
    </trl>
    """
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
        print(_HELP)
        sys.exit(0)
    if len(sys.argv) < 2:
        print(_HELP)
        sys.exit(1)

    if sys.argv[1] == "--all":
        directory = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        files = sorted(
            set(directory.rglob("*.trug.json")) | set(directory.rglob("*.json"))
        )
        if not files:
            print(f"No .trug.json files found in {directory}")
            sys.exit(1)
        total_errors = 0
        for f in files:
            result = validate_file(f)
            status = "PASS" if result.valid else "FAIL"
            print(f"  {status}  {f}  ({result.summary()})")
            total_errors += len(result.errors)
            for err in result.errors:
                print(f"         {err.code}: {err.message}")
            for warn in result.warnings:
                print(f"         WARN {warn.code}: {warn.message}")
        print(f"\n{len(files)} files checked, {total_errors} errors")
        sys.exit(1 if total_errors > 0 else 0)
    else:
        path = Path(sys.argv[1])
        result = validate_file(path)
        if result.valid:
            print(f"VALID  {path}")
            for warn in result.warnings:
                print(f"  WARN {warn.code}: {warn.message}")
            sys.exit(0)
        else:
            print(f"INVALID  {path}")
            for err in result.errors:
                print(f"  ERROR {err.code}: {err.message}")
            for warn in result.warnings:
                print(f"  WARN {warn.code}: {warn.message}")
            sys.exit(1)


if __name__ == "__main__":
    main()
