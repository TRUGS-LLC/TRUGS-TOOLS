#!/usr/bin/env python3
"""
AAA.md Validator

Validates AAA.md files have:
1. All 9 required sections (AAA Protocol v2)
2. ARCHITECTURE section has content (System Design and/or Issue TRUG)

v2 phases: VISION → FEASIBILITY → SPECIFICATIONS → ARCHITECTURE →
           VALIDATION → CODING → TESTING → AUDIT → DEPLOYMENT
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REQUIRED_PHASES = [
    "VISION",
    "FEASIBILITY",
    "SPECIFICATIONS",
    "ARCHITECTURE",
    "VALIDATION",
    "CODING",
    "TESTING",
    "AUDIT",
    "DEPLOYMENT",
]

# Accept legacy 7-phase files during transition
LEGACY_PHASES = [
    "VISION",
    "FEASIBILITY",
    "SPECIFICATIONS",
    "ARCHITECTURE",
    "CODING",
    "TESTING",
    "DEPLOYMENT",
]

AAA_V1_NODE_TYPES = {
    "AAA",
    "PHASE",
    "TASK",
    "AUDIT",
    "RISK",
    "ADR",
    "DEPENDENCY",
    "RESEARCH_SOURCE",
    "QUALITY_GATE",
    "SUB_ISSUE",
}
CORE_NODE_FIELDS = {"id", "type", "properties", "parent_id", "contains", "metric_level", "dimension"}
CORE_EDGE_FIELDS = {"from_id", "to_id", "relation"}

def parse_sections(content: str) -> List[str]:
    """Extract ## section headers from markdown."""
    pattern = r'^## ([A-Z_\s]+)$'
    sections = re.findall(pattern, content, re.MULTILINE)
    return [s.strip() for s in sections]

def check_issue_trug(content: str) -> bool:
    """Check if ARCHITECTURE section contains an Issue TRUG (JSON block with nodes and edges).

    Returns True if a valid Issue TRUG JSON block is present, False otherwise.
    Note: A False result does NOT mean the ARCHITECTURE section is invalid —
    Issue TRUG is optional. System Design content alone is sufficient.
    """
    # Find ARCHITECTURE section
    pattern = r'## ARCHITECTURE.*?(?=\n## |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return False

    arch_section = match.group(0)

    # Extract content of ```json ... ``` code block
    json_block_match = re.search(r'```json(.*?)```', arch_section, re.DOTALL)
    if not json_block_match:
        return False

    block_content = json_block_match.group(1)
    return bool(re.search(r'"nodes"', block_content)) and bool(re.search(r'"edges"', block_content))

def check_architecture_content(content: str) -> bool:
    """Check if ARCHITECTURE section has meaningful content.

    ARCHITECTURE is valid if it contains EITHER:
    - System Design content (any non-trivial text beyond the heading), OR
    - A valid Issue TRUG JSON block, OR
    - Both
    """
    pattern = r'## ARCHITECTURE(.*?)(?=\n## |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return False

    arch_body = match.group(1).strip()

    # Must have some content beyond just the heading
    # Strip phase status line and check what remains
    lines = [
        line.strip() for line in arch_body.splitlines()
        if line.strip() and not line.strip().startswith("**Phase Status:**")
    ]
    return len(lines) > 0

def validate_aaa(filepath: Path) -> Tuple[bool, List[str]]:
    """
    Validate AAA.md file.
    
    Returns:
        (is_valid, errors)
    """
    if not filepath.exists():
        return False, [f"File not found: {filepath}"]
    
    content = filepath.read_text()
    sections = parse_sections(content)
    errors = []
    
    # Check phases present — accept v2 (9 phases) or legacy v1 (7 phases)
    missing_v2 = [p for p in REQUIRED_PHASES if p not in sections]
    missing_v1 = [p for p in LEGACY_PHASES if p not in sections]

    if missing_v2 and missing_v1:
        # Neither v1 nor v2 complete — report against v2
        errors.append(f"Missing required sections: {', '.join(missing_v2)}")
    elif not missing_v2:
        pass  # v2 complete
    elif not missing_v1:
        pass  # legacy v1 complete (acceptable during transition)
    
    # Check ARCHITECTURE has content (System Design and/or Issue TRUG)
    if "ARCHITECTURE" in sections:
        if not check_architecture_content(content):
            errors.append("ARCHITECTURE section is empty (needs System Design and/or Issue TRUG)")
    
    return len(errors) == 0, errors


def validate_aaa_trug(trug: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an AAA TRUG document and aaa_v1 pairing rules."""
    errors: List[str] = []

    trug_type = trug.get("type")
    if trug_type != "AAA":
        errors.append(f"TRUG type must be 'AAA', found '{trug_type}'")

    vocabularies = trug.get("vocabularies")
    if not isinstance(vocabularies, list):
        vocabularies = trug.get("capabilities", {}).get("vocabularies", [])
    if "aaa_v1" not in vocabularies:
        errors.append(f"TRUG vocabularies must include 'aaa_v1', found {vocabularies}")

    nodes = trug.get("nodes", [])
    edges = trug.get("edges", [])
    node_ids = set()
    for index, node in enumerate(nodes):
        missing = sorted(CORE_NODE_FIELDS - set(node.keys()))
        if missing:
            errors.append(f"Node at index {index} missing CORE fields: {', '.join(missing)}")
            continue
        node_ids.add(node["id"])
        if node.get("type") not in AAA_V1_NODE_TYPES:
            errors.append(f"Node '{node.get('id')}' has unknown aaa_v1 node type '{node.get('type')}'")

    for index, edge in enumerate(edges):
        missing = sorted(CORE_EDGE_FIELDS - set(edge.keys()))
        if missing:
            errors.append(f"Edge at index {index} missing CORE fields: {', '.join(missing)}")
            continue
        from_id = edge.get("from_id")
        to_id = edge.get("to_id")
        if from_id not in node_ids or to_id not in node_ids:
            errors.append(
                f"Dangling edge {index}: {from_id} -[{edge.get('relation')}]-> {to_id} references missing node ID(s)"
            )

    coding_phase_ids = {
        node["id"]
        for node in nodes
        if node.get("type") == "PHASE"
        and str(node.get("properties", {}).get("name", "")).upper() == "CODING"
    }

    audited_task_ids = {
        edge.get("to_id")
        for edge in edges
        if edge.get("relation") == "audits"
        and any(n.get("id") == edge.get("from_id") and n.get("type") == "AUDIT" for n in nodes)
    }

    for node in nodes:
        if node.get("type") != "TASK":
            continue
        if node.get("parent_id") not in coding_phase_ids:
            continue
        if node.get("id") not in audited_task_ids:
            task_name = node.get("properties", {}).get("name", "")
            errors.append(f"Unpaired CODING task '{node.get('id')}' ({task_name}) has no AUDIT via 'audits' edge")

    return len(errors) == 0, errors

def main():
    if len(sys.argv) < 2:
        print("Usage: aaa-validate <path/to/AAA.md>")
        sys.exit(1)
    
    filepath = Path(sys.argv[1])
    is_valid, errors = validate_aaa(filepath)
    
    if is_valid:
        print(f"✓ {filepath} is valid")
        sys.exit(0)
    else:
        print(f"✗ {filepath} validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

if __name__ == "__main__":
    main()
