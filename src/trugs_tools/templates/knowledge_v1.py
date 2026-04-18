"""Knowledge_v1 branch templates for TRUGS generator.

Unified vocabulary merging Living (persistent memory), Knowledge (ontology),
Research (bibliographic), and Decision (architectural conclusions).

Replaces the former living.py, knowledge.py, and research.py templates.
See BRANCHES.md knowledge_v1 section and issue #622/#620.
"""

from typing import Dict, Any


def generate_knowledge_v1_minimal() -> Dict[str, Any]:
    """Generate minimal knowledge_v1 TRUG (4 nodes).

    Demonstrates the merge: KNOWLEDGE_GRAPH root, QUERY (Living origin),
    ENTITY (shared), DECISION (from #620).

    Returns:
        Valid TRUG dictionary for knowledge_v1 branch
    """
    return {
        "name": "Knowledge_v1 Minimal Example",
        "version": "1.0.0",
        "type": "KNOWLEDGE",
        "branch": "knowledge_v1",
        "description": "Minimal knowledge_v1 TRUG demonstrating merged vocabulary",
        "dimensions": {
            "knowledge_flow": {
                "description": "Knowledge acquisition and decision-making flow",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["knowledge_v1"],
            "profiles": []
        },
        "nodes": [
            {
                "id": "kg_root",
                "type": "KNOWLEDGE_GRAPH",
                "metric_level": "KILO_KNOWLEDGE_GRAPH",
                "parent_id": None,
                "contains": ["query_1", "entity_1", "decision_1"],
                "properties": {
                    "name": "Example Knowledge Graph",
                    "description": "Minimal example demonstrating knowledge_v1 vocabulary"
                }
            },
            {
                "id": "query_1",
                "type": "QUERY",
                "metric_level": "BASE_QUERY",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Initial Query",
                    "text": "What graph database should we use?",
                    "intent": "evaluation"
                }
            },
            {
                "id": "entity_1",
                "type": "ENTITY",
                "metric_level": "BASE_ENTITY",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Neo4j",
                    "description": "Popular graph database with ACID transactions",
                    "entity_type": "technology"
                }
            },
            {
                "id": "decision_1",
                "type": "DECISION",
                "metric_level": "BASE_DECISION",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Database Selection",
                    "decision": "Use file-based storage for MVP, defer database selection",
                    "decision_type": "architectural",
                    "rationale": "MVP has fewer than 10K nodes; database adds operational complexity without proportional benefit",
                    "constraints": ["No PostgreSQL dependency at MVP launch"],
                    "reversible_by": "Reaching 10K+ nodes or needing concurrent writers"
                }
            }
        ],
        "edges": [
            {"from_id": "kg_root", "to_id": "query_1", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "entity_1", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "decision_1", "relation": "contains"},
            {"from_id": "query_1", "to_id": "entity_1", "relation": "produces"},
            {"from_id": "decision_1", "to_id": "entity_1", "relation": "rejects", "weight": 0.8}
        ]
    }


def generate_knowledge_v1_complete() -> Dict[str, Any]:
    """Generate complete knowledge_v1 TRUG with all three origin domains.

    Demonstrates Living flow (query → tool → entity → synthesis → answer),
    Knowledge ontology (class → entity → instance), Research sources
    (web_source, paper, claim), and Decision vocabulary (decision with
    rejects/supersedes/invalidates edges).

    Returns:
        Valid TRUG dictionary for knowledge_v1 branch with full vocabulary
    """
    return {
        "name": "Knowledge_v1 Complete Example",
        "version": "1.0.0",
        "type": "KNOWLEDGE",
        "branch": "knowledge_v1",
        "description": "Complete knowledge_v1 TRUG demonstrating all 16 node types and decision discourse",
        "dimensions": {
            "knowledge_flow": {
                "description": "Knowledge acquisition, reasoning, and decision-making",
                "base_level": "BASE"
            }
        },
        "capabilities": {
            "extensions": [],
            "vocabularies": ["knowledge_v1"],
            "profiles": []
        },
        "nodes": [
            # Root
            {
                "id": "kg_root",
                "type": "KNOWLEDGE_GRAPH",
                "metric_level": "KILO_KNOWLEDGE_GRAPH",
                "parent_id": None,
                "contains": [
                    "query_eval", "tool_search", "entity_neo4j",
                    "synthesis_comparison", "answer_recommendation",
                    "class_database", "concept_acid",
                    "source_docs", "author_neo4j_inc", "paper_survey",
                    "claim_performance", "version_5",
                    "decision_architecture", "proposal_rejected"
                ],
                "properties": {
                    "name": "Technology Evaluation",
                    "description": "Complete knowledge graph for database technology evaluation"
                }
            },
            # Living: Query → Tool → Entity → Synthesis → Answer
            {
                "id": "query_eval",
                "type": "QUERY",
                "metric_level": "BASE_QUERY",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Evaluation Query",
                    "text": "Compare graph database options for our project",
                    "intent": "evaluation",
                    "timestamp": "2026-03-15T10:00:00Z"
                }
            },
            {
                "id": "tool_search",
                "type": "TOOL_EXECUTION",
                "metric_level": "MILLI_TOOL_EXECUTION",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Web Search",
                    "tool_name": "web_search",
                    "parameters": {"q": "graph database comparison 2026"},
                    "status": "completed",
                    "duration_ms": 350
                }
            },
            {
                "id": "entity_neo4j",
                "type": "ENTITY",
                "metric_level": "BASE_ENTITY",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Neo4j",
                    "description": "Native graph database with Cypher query language",
                    "entity_type": "technology"
                }
            },
            {
                "id": "synthesis_comparison",
                "type": "SYNTHESIS",
                "metric_level": "BASE_SYNTHESIS",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Database Comparison",
                    "summary": "Neo4j offers mature graph capabilities but adds operational complexity vs file-based approach",
                    "confidence": 0.9,
                    "sources_count": 3
                }
            },
            {
                "id": "answer_recommendation",
                "type": "ANSWER",
                "metric_level": "BASE_ANSWER",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Final Recommendation",
                    "text": "Defer database selection until node count exceeds 10K. Use file-based JSON storage for MVP.",
                    "format": "natural_language"
                }
            },
            # Knowledge: Class → Entity (ontology)
            {
                "id": "class_database",
                "type": "CLASS",
                "metric_level": "KILO_CLASS",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Graph Database",
                    "description": "Database systems using graph structures for data storage and querying",
                    "domain": "technology"
                }
            },
            {
                "id": "concept_acid",
                "type": "CONCEPT",
                "metric_level": "BASE_CONCEPT",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "ACID Transactions",
                    "description": "Atomicity, Consistency, Isolation, Durability guarantees"
                }
            },
            # Research: Source → Claim, Author, Paper, Version
            {
                "id": "source_docs",
                "type": "WEB_SOURCE",
                "metric_level": "BASE_WEB_SOURCE",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Neo4j Documentation",
                    "url": "https://neo4j.com/docs",
                    "title": "Neo4j Official Documentation",
                    "accessed_date": "2026-03-15"
                }
            },
            {
                "id": "author_neo4j_inc",
                "type": "AUTHOR",
                "metric_level": "BASE_AUTHOR",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Neo4j Inc.",
                    "organization": "Neo4j Inc."
                }
            },
            {
                "id": "paper_survey",
                "type": "PAPER",
                "metric_level": "BASE_PAPER",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Graph Database Survey",
                    "title": "A Survey of Graph Database Technologies",
                    "published_date": "2025-06-01",
                    "description": "Comparative analysis of graph database systems"
                }
            },
            {
                "id": "claim_performance",
                "type": "CLAIM",
                "metric_level": "CENTI_CLAIM",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Performance Claim",
                    "claim_text": "Neo4j handles 10M+ nodes with sub-second traversal",
                    "source_id": "source_docs",
                    "confidence": 0.85
                }
            },
            {
                "id": "version_5",
                "type": "VERSION",
                "metric_level": "CENTI_VERSION",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Neo4j 5.x",
                    "version_string": "5.0.0",
                    "release_date": "2022-10-27",
                    "status": "active"
                }
            },
            # Decision: Architectural conclusion with rejection
            {
                "id": "decision_architecture",
                "type": "DECISION",
                "metric_level": "BASE_DECISION",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Storage Architecture Decision",
                    "decision": "Use file-based JSON storage for MVP; defer PostgreSQL until 10K+ nodes",
                    "decision_type": "architectural",
                    "rationale": "File-based storage eliminates operational complexity. trugs-store abstracts the backend, making future migration seamless.",
                    "constraints": ["No database dependency at MVP", "Must support < 1s read for typical folder TRUGs"],
                    "reversible_by": "Node count exceeding 10K or need for concurrent writers"
                }
            },
            {
                "id": "proposal_rejected",
                "type": "ENTITY",
                "metric_level": "BASE_ENTITY",
                "parent_id": "kg_root",
                "contains": [],
                "properties": {
                    "name": "Neo4j for MVP Proposal",
                    "description": "Proposal to use Neo4j as primary storage from day one",
                    "entity_type": "proposal"
                }
            }
        ],
        "edges": [
            # Containment hierarchy
            {"from_id": "kg_root", "to_id": "query_eval", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "tool_search", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "entity_neo4j", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "synthesis_comparison", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "answer_recommendation", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "class_database", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "concept_acid", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "source_docs", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "author_neo4j_inc", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "paper_survey", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "claim_performance", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "version_5", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "decision_architecture", "relation": "contains"},
            {"from_id": "kg_root", "to_id": "proposal_rejected", "relation": "contains"},
            # Living flow
            {"from_id": "query_eval", "to_id": "tool_search", "relation": "triggers", "weight": 0.9},
            {"from_id": "tool_search", "to_id": "entity_neo4j", "relation": "produces"},
            {"from_id": "entity_neo4j", "to_id": "synthesis_comparison", "relation": "synthesizes_to"},
            {"from_id": "synthesis_comparison", "to_id": "answer_recommendation", "relation": "produces", "weight": 0.95},
            {"from_id": "answer_recommendation", "to_id": "entity_neo4j", "relation": "cites"},
            # Knowledge ontology
            {"from_id": "entity_neo4j", "to_id": "class_database", "relation": "is_a"},
            {"from_id": "entity_neo4j", "to_id": "concept_acid", "relation": "has_property", "weight": 0.9},
            # Research references
            {"from_id": "source_docs", "to_id": "claim_performance", "relation": "supports", "weight": 0.85},
            {"from_id": "source_docs", "to_id": "author_neo4j_inc", "relation": "authored_by"},
            {"from_id": "paper_survey", "to_id": "entity_neo4j", "relation": "defines"},
            {"from_id": "version_5", "to_id": "entity_neo4j", "relation": "depends_on"},
            # Decision discourse
            {"from_id": "decision_architecture", "to_id": "proposal_rejected", "relation": "rejects"},
            {"from_id": "decision_architecture", "to_id": "synthesis_comparison", "relation": "supersedes"}
        ]
    }
