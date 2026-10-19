# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Supplementary structural-analysis checks (unreachable / dead nodes).

The canonical validator is `trugs_tools.validate` (CORE-16 — exactly
what `trug validate` runs). This module is NOT a verdict authority: it holds only
`validate_rule_10_unreachable_nodes` and `validate_rule_11_dead_nodes`, called by
`validate_trug` as verdict-NEUTRAL warnings. The legacy `validate_rule_1..9` +
`validate_required_root_fields` (~500 lines of a second, drift-prone copy of the
ruleset) were removed — the CORE verdict
rules live in `validate.py`; edit THAT file, never this one, for verdict changes.

<trl>
PROCESS rules SHALL VALIDATE RECORD trug_graph AGAINST DATA validation_rule AND EMIT RECORD validation_result.
</trl>
"""

from typing import Any, Dict

from trugs_tools.errors import ValidationResult


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
