"""
TRUGS Web Module

Async web crawling, entity/relation extraction, resolution, and TRUGS 1.0
graph building from web sources.

Optional dependencies (install with `pip install trugs-tools[web,llm]`):
  - httpx, beautifulsoup4, lxml  (web)
  - anthropic, openai            (llm)
"""

from .crawler import Source, SourceDiscoverer, discover_sources
from .extractor import (
    Entity,
    Relation,
    LLMClient,
    MockLLMClient,
    AnthropicClient,
    OpenAIClient,
    EntityExtractor,
    RelationExtractor,
    CitationExtractor,
    create_extractor,
)
from .resolver import ResolvedEntity, EntityResolver, CrossReferenceMapper, resolve_entities
from .credibility import CredibilityFactors, CredibilityScorer, calculate_credibility, score_edge_weight
from .graph_builder import TRUGSWebGraphBuilder, build_graph, load_graph, url_to_id, make_id  # builds TRUGS 1.0 graph from raw web data
from .query import (
    Node,
    Edge,
    GraphMeta,
    Graph,
    GraphLoader,
    load_graph as load_query_graph,  # loads a pre-built TRUGS 1.0 graph for querying
    TraversalResult,
    GraphTraverser,
    query_graph,
    Finding,
    Report,
    ReportSynthesizer,
    generate_report,
)
from .hub import (
    QualifyingInterest,
    parse_qualifying_interest,
    match_interest,
    rank_matches,
    HubCandidate,
    HubAgent,
    CrossTrugUri,
    CrossTrugEdge,
    parse_cross_trug_uri,
    is_cross_trug_ref,
    build_cross_trug_uri,
    validate_cross_trug_edge,
    CrossTrugResolver,
    Orchestrator,
    PipelineResult,
)
from .refresh import (
    PersistentQuery,
    QueryStore,
    QueryRunner,
    QueryDiffResult,
    TrugDiff,
    diff_trugs,
    apply_diff,
)
from .weight import (
    NodeTopology,
    compute_topology,
    rank_by_importance,
    find_convergence,
    compute_freshness,
)

__all__ = [
    # crawler
    "Source",
    "SourceDiscoverer",
    "discover_sources",
    # extractor
    "Entity",
    "Relation",
    "LLMClient",
    "MockLLMClient",
    "AnthropicClient",
    "OpenAIClient",
    "EntityExtractor",
    "RelationExtractor",
    "CitationExtractor",
    "create_extractor",
    # resolver
    "ResolvedEntity",
    "EntityResolver",
    "CrossReferenceMapper",
    "resolve_entities",
    # credibility
    "CredibilityFactors",
    "CredibilityScorer",
    "calculate_credibility",
    "score_edge_weight",
    # graph_builder
    "TRUGSWebGraphBuilder",
    "build_graph",
    "load_graph",
    "url_to_id",
    "make_id",
    # query
    "Node",
    "Edge",
    "GraphMeta",
    "Graph",
    "GraphLoader",
    "load_query_graph",
    "TraversalResult",
    "GraphTraverser",
    "query_graph",
    "Finding",
    "Report",
    "ReportSynthesizer",
    "generate_report",
    # hub
    "QualifyingInterest",
    "parse_qualifying_interest",
    "match_interest",
    "rank_matches",
    "HubCandidate",
    "HubAgent",
    "CrossTrugUri",
    "CrossTrugEdge",
    "parse_cross_trug_uri",
    "is_cross_trug_ref",
    "build_cross_trug_uri",
    "validate_cross_trug_edge",
    "CrossTrugResolver",
    "Orchestrator",
    "PipelineResult",
    # refresh
    "PersistentQuery",
    "QueryStore",
    "QueryRunner",
    "QueryDiffResult",
    "TrugDiff",
    "diff_trugs",
    "apply_diff",
    # weight
    "NodeTopology",
    "compute_topology",
    "rank_by_importance",
    "find_convergence",
    "compute_freshness",
]
