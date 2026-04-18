"""Orchestration branch templates for TRUGS generator.

Multi-agent coordination templates modeling agent hierarchies,
task delegation, resource access, and escalation paths.
"""

from typing import Dict, Any


def generate_orchestration_minimal() -> Dict[str, Any]:
    """Generate minimal Orchestration TRUG (3 nodes).

    Structure:
    - 1 AGENT (root)
    - 1 TASK (child of agent)
    - 1 ESCALATION (child of task)

    Returns:
        Valid TRUG dictionary for multi-agent coordination
    """
    return {
        "name": "Orchestration Minimal Example",
        "version": "1.0.0",
        "type": "ORCHESTRATION",
        "branch": "orchestration",
        "description": "Minimal Orchestration TRUG demonstrating agent-task-escalation chain",
        "nodes": [
            {
                "id": "agent_1",
                "type": "AGENT",
                "metric_level": "DEKA_AGENT",
                "parent_id": None,
                "properties": {
                    "name": "Primary Agent",
                    "role": "coordinator",
                    "description": "Root agent coordinating task execution"
                }
            },
            {
                "id": "task_1",
                "type": "TASK",
                "metric_level": "BASE_TASK",
                "parent_id": "agent_1",
                "properties": {
                    "name": "Data Processing",
                    "status": "pending",
                    "priority": "high"
                }
            },
            {
                "id": "escalation_1",
                "type": "ESCALATION",
                "metric_level": "MILLI_ESCALATION",
                "parent_id": "task_1",
                "properties": {
                    "trigger": "timeout",
                    "threshold": "30s",
                    "action": "notify_principal"
                }
            }
        ],
        "edges": [
            {"from_id": "agent_1", "to_id": "task_1", "relation": "contains"},
            {"from_id": "task_1", "to_id": "escalation_1", "relation": "contains"},
            {"from_id": "escalation_1", "to_id": "agent_1", "relation": "escalates_to"}
        ],
        "dimensions": [
            {
                "name": "agent_hierarchy",
                "levels": ["PRINCIPAL", "AGENT", "TASK"]
            }
        ]
    }


def generate_orchestration_complete() -> Dict[str, Any]:
    """Generate complete Orchestration TRUG with delegation and escalation.

    Returns:
        Valid TRUG dictionary for multi-agent coordination with
        principals, agents, tasks, resources, permissions, and escalation
    """
    return {
        "name": "Orchestration Complete Example",
        "version": "1.0.0",
        "type": "ORCHESTRATION",
        "branch": "orchestration",
        "description": "Complete Orchestration TRUG with multi-agent delegation and escalation",
        "nodes": [
            {
                "id": "principal_1",
                "type": "PRINCIPAL",
                "metric_level": "HECTO_PRINCIPAL",
                "parent_id": None,
                "properties": {
                    "name": "System Administrator",
                    "authority_level": "root",
                    "description": "Top-level principal overseeing all agents"
                }
            },
            {
                "id": "agent_coordinator",
                "type": "AGENT",
                "metric_level": "DEKA_AGENT",
                "parent_id": "principal_1",
                "properties": {
                    "name": "Coordinator Agent",
                    "role": "coordinator",
                    "description": "Delegates tasks across worker agents"
                }
            },
            {
                "id": "agent_worker",
                "type": "AGENT",
                "metric_level": "DEKA_AGENT",
                "parent_id": "principal_1",
                "properties": {
                    "name": "Worker Agent",
                    "role": "executor",
                    "description": "Executes assigned tasks"
                }
            },
            {
                "id": "task_ingest",
                "type": "TASK",
                "metric_level": "BASE_TASK",
                "parent_id": "agent_coordinator",
                "properties": {
                    "name": "Data Ingestion",
                    "status": "active",
                    "priority": "high"
                }
            },
            {
                "id": "task_transform",
                "type": "TASK",
                "metric_level": "BASE_TASK",
                "parent_id": "agent_worker",
                "properties": {
                    "name": "Data Transformation",
                    "status": "pending",
                    "priority": "medium"
                }
            },
            {
                "id": "resource_db",
                "type": "RESOURCE",
                "metric_level": "KILO_RESOURCE",
                "parent_id": "principal_1",
                "properties": {
                    "name": "Primary Database",
                    "resource_type": "database",
                    "uri": "postgres://db.internal:5432/main"
                }
            },
            {
                "id": "permission_rw",
                "type": "PERMISSION",
                "metric_level": "MILLI_PERMISSION",
                "parent_id": "resource_db",
                "properties": {
                    "scope": "read_write",
                    "grantee": "agent_worker",
                    "expires": "2025-12-31"
                }
            },
            {
                "id": "escalation_timeout",
                "type": "ESCALATION",
                "metric_level": "MILLI_ESCALATION",
                "parent_id": "task_ingest",
                "properties": {
                    "trigger": "timeout",
                    "threshold": "60s",
                    "action": "reassign_to_coordinator"
                }
            }
        ],
        "edges": [
            # Containment hierarchy
            {"from_id": "principal_1", "to_id": "agent_coordinator", "relation": "contains"},
            {"from_id": "principal_1", "to_id": "agent_worker", "relation": "contains"},
            {"from_id": "principal_1", "to_id": "resource_db", "relation": "contains"},
            {"from_id": "agent_coordinator", "to_id": "task_ingest", "relation": "contains"},
            {"from_id": "agent_worker", "to_id": "task_transform", "relation": "contains"},
            {"from_id": "resource_db", "to_id": "permission_rw", "relation": "contains"},
            {"from_id": "task_ingest", "to_id": "escalation_timeout", "relation": "contains"},
            # Delegation and reporting
            {"from_id": "agent_coordinator", "to_id": "agent_worker", "relation": "delegates_to", "weight": 0.95},
            {"from_id": "agent_worker", "to_id": "agent_coordinator", "relation": "reports_to"},
            {"from_id": "agent_coordinator", "to_id": "principal_1", "relation": "reports_to"},
            # Authorization
            {"from_id": "permission_rw", "to_id": "agent_worker", "relation": "authorizes", "weight": 0.9},
            # Resource access
            {"from_id": "agent_worker", "to_id": "resource_db", "relation": "accesses"},
            # Escalation
            {"from_id": "escalation_timeout", "to_id": "agent_coordinator", "relation": "escalates_to"}
        ],
        "dimensions": [
            {
                "name": "agent_hierarchy",
                "levels": ["PRINCIPAL", "AGENT", "TASK"]
            }
        ]
    }
