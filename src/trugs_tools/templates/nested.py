"""Nested branch templates for TRUGS generator.

Hierarchical graph composition templates modeling parent-subgraph
relationships via reference — sub-graphs are loaded lazily with
no ID conflicts between levels.
"""

from typing import Dict, Any


def generate_nested_minimal() -> Dict[str, Any]:
    """Generate minimal Nested TRUG (3 nodes).

    Structure:
    - 1 TASK (root)
    - 2 SUBGRAPH (child references)

    Returns:
        Valid TRUG dictionary for hierarchical graph composition
    """
    return {
        "name": "Nested Minimal Example",
        "version": "1.0.0",
        "type": "NESTED",
        "branch": "nested",
        "description": "Minimal Nested TRUG demonstrating parent-subgraph composition",
        "nodes": [
            {
                "id": "task_root",
                "type": "TASK",
                "metric_level": "BASE_TASK",
                "parent_id": None,
                "properties": {
                    "name": "Data Pipeline",
                    "description": "Top-level pipeline task",
                    "status": "pending"
                }
            },
            {
                "id": "subgraph_ingest",
                "type": "SUBGRAPH",
                "metric_level": "DEKA_SUBGRAPH",
                "parent_id": "task_root",
                "properties": {
                    "name": "Ingest Workflow",
                    "subgraph_ref": "ingest_workflow.trug.json",
                    "description": "External child graph: data ingestion steps"
                }
            },
            {
                "id": "subgraph_transform",
                "type": "SUBGRAPH",
                "metric_level": "DEKA_SUBGRAPH",
                "parent_id": "task_root",
                "properties": {
                    "name": "Transform Workflow",
                    "subgraph_ref": "transform_workflow.trug.json",
                    "description": "External child graph: data transformation steps"
                }
            }
        ],
        "edges": [
            {"from_id": "task_root", "to_id": "subgraph_ingest", "relation": "contains"},
            {"from_id": "task_root", "to_id": "subgraph_transform", "relation": "contains"},
            {"from_id": "subgraph_ingest", "to_id": "subgraph_transform", "relation": "precedes"}
        ],
        "dimensions": [
            {
                "name": "execution_flow",
                "levels": ["TASK", "SUBGRAPH"]
            }
        ]
    }


def generate_nested_complete() -> Dict[str, Any]:
    """Generate complete Nested TRUG with tasks, subgraphs, and results (7 nodes).

    Returns:
        Valid TRUG dictionary for hierarchical graph composition with
        tasks, subgraph references, and result outcomes
    """
    return {
        "name": "Nested Complete Example",
        "version": "1.0.0",
        "type": "NESTED",
        "branch": "nested",
        "description": "Complete Nested TRUG with tasks, subgraphs, and results",
        "nodes": [
            {
                "id": "task_root",
                "type": "TASK",
                "metric_level": "BASE_TASK",
                "parent_id": None,
                "properties": {
                    "name": "Data Pipeline",
                    "description": "Top-level data processing pipeline",
                    "status": "running"
                }
            },
            {
                "id": "task_validate",
                "type": "TASK",
                "metric_level": "BASE_TASK",
                "parent_id": "task_root",
                "properties": {
                    "name": "Validate Outputs",
                    "description": "Validate all pipeline outputs",
                    "status": "pending"
                }
            },
            {
                "id": "subgraph_ingest",
                "type": "SUBGRAPH",
                "metric_level": "DEKA_SUBGRAPH",
                "parent_id": "task_root",
                "properties": {
                    "name": "Ingest Workflow",
                    "subgraph_ref": "ingest_workflow.trug.json",
                    "description": "External child graph: data ingestion steps"
                }
            },
            {
                "id": "subgraph_transform",
                "type": "SUBGRAPH",
                "metric_level": "DEKA_SUBGRAPH",
                "parent_id": "task_root",
                "properties": {
                    "name": "Transform Workflow",
                    "subgraph_ref": "transform_workflow.trug.json",
                    "description": "External child graph: data transformation steps"
                }
            },
            {
                "id": "subgraph_load",
                "type": "SUBGRAPH",
                "metric_level": "DEKA_SUBGRAPH",
                "parent_id": "task_root",
                "properties": {
                    "name": "Load Workflow",
                    "subgraph_ref": "load_workflow.trug.json",
                    "description": "External child graph: data loading to warehouse"
                }
            },
            {
                "id": "result_ingest",
                "type": "RESULT",
                "metric_level": "MILLI_RESULT",
                "parent_id": "subgraph_ingest",
                "properties": {
                    "name": "Ingest Output",
                    "status": "success",
                    "records_processed": 50000
                }
            },
            {
                "id": "result_pipeline",
                "type": "RESULT",
                "metric_level": "MILLI_RESULT",
                "parent_id": "task_root",
                "properties": {
                    "name": "Pipeline Result",
                    "status": "success",
                    "summary": "All stages completed"
                }
            }
        ],
        "edges": [
            # Containment hierarchy
            {"from_id": "task_root", "to_id": "task_validate", "relation": "contains"},
            {"from_id": "task_root", "to_id": "subgraph_ingest", "relation": "contains"},
            {"from_id": "task_root", "to_id": "subgraph_transform", "relation": "contains"},
            {"from_id": "task_root", "to_id": "subgraph_load", "relation": "contains"},
            {"from_id": "task_root", "to_id": "result_pipeline", "relation": "contains"},
            {"from_id": "subgraph_ingest", "to_id": "result_ingest", "relation": "contains"},
            # Execution flow
            {"from_id": "subgraph_ingest", "to_id": "subgraph_transform", "relation": "precedes", "weight": 0.9},
            {"from_id": "subgraph_transform", "to_id": "subgraph_load", "relation": "precedes", "weight": 0.9},
            {"from_id": "subgraph_load", "to_id": "task_validate", "relation": "precedes", "weight": 0.9},
            {"from_id": "subgraph_ingest", "to_id": "result_ingest", "relation": "produces", "weight": 0.8},
            {"from_id": "task_validate", "to_id": "result_pipeline", "relation": "produces", "weight": 0.8}
        ],
        "dimensions": [
            {
                "name": "execution_flow",
                "levels": ["TASK", "SUBGRAPH", "RESULT"]
            }
        ]
    }
