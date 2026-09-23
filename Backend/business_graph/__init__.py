"""
RetailAsk Business Graph (Step 3B).

Graph representation + construction + traversal only.
Persistent store: Neo4j. Fallback/tests: in-memory.
Not Schema RAG. Not NL→graph Q&A. Not agents.
"""

from .models import NodeLabel, RelType
from .store import GraphStore, InMemoryGraphStore
from .neo4j_store import Neo4jGraphStore, neo4j_config_from_env
from .builder import BusinessGraphBuilder, BuildStats
from .service import BusinessGraphService
from .retriever import GraphRetriever, format_retrieval_report
from .intent import RetrievalIntent, parse_retrieval_intent
from .graph_answer import generate_graph_answer, run_graph_rag

__all__ = [
    'NodeLabel',
    'RelType',
    'GraphStore',
    'InMemoryGraphStore',
    'Neo4jGraphStore',
    'neo4j_config_from_env',
    'BusinessGraphBuilder',
    'BuildStats',
    'BusinessGraphService',
    'GraphRetriever',
    'format_retrieval_report',
    'RetrievalIntent',
    'parse_retrieval_intent',
    'generate_graph_answer',
    'run_graph_rag',
]
