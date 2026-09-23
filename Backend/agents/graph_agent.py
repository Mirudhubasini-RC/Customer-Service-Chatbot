"""
Graph Agent (Step 4C) — relationship analytics via Graph Retrieval + Graph RAG.

Orchestrates existing business_graph capabilities; does not duplicate retrieval
or answer-generation logic. Independent of the Supervisor (not wired yet).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger('retail-agent')

RetrieveFn = Callable[[str], dict[str, Any]]
GenerateAnswerFn = Callable[[str, dict[str, Any]], str]

INSUFFICIENT_ANSWER = (
    'The available Neo4j graph data is insufficient to answer this question. '
    'No matching business-graph facts were retrieved.'
)


def _failure(
    question: str,
    *,
    retrieval: dict[str, Any] | None = None,
    answer: str,
    error: str,
    source: str = 'neo4j',
) -> dict[str, Any]:
    return {
        'agent': 'graph',
        'question': question,
        'retrieval': retrieval if retrieval is not None else {},
        'answer': answer,
        'source': source,
        'success': False,
        'error': error,
    }


def _success(
    question: str,
    *,
    retrieval: dict[str, Any],
    answer: str,
    source: str = 'neo4j',
) -> dict[str, Any]:
    return {
        'agent': 'graph',
        'question': question,
        'retrieval': retrieval,
        'answer': answer,
        'source': source,
        'success': True,
        'error': None,
    }


def run_graph_agent(
    question: str,
    *,
    retrieve_fn: RetrieveFn | None = None,
    generate_answer_fn: GenerateAnswerFn | None = None,
    store: Any | None = None,
) -> dict[str, Any]:
    """
    Run the Graph Agent pipeline for a relationship / traversal question.

    Flow: GraphRetriever → Neo4j → graph context → generate_graph_answer → NL.

    Injectable callables are for unit tests. Production uses Neo4jGraphStore
    + GraphRetriever + generate_graph_answer.
    """
    q = (question or '').strip()
    if not q:
        return _failure(
            '',
            answer='Please ask a business-graph analytics question.',
            error='empty_question',
        )

    owned_store = None
    try:
        if retrieve_fn is None or generate_answer_fn is None:
            from business_graph.graph_answer import (
                generate_graph_answer,
                is_insufficient_retrieval,
            )

            if retrieve_fn is None:
                if store is None:
                    from business_graph import Neo4jGraphStore

                    owned_store = Neo4jGraphStore.from_env()
                    store = owned_store
                from business_graph.retriever import GraphRetriever

                retrieve_fn = GraphRetriever(store).retrieve

            if generate_answer_fn is None:
                generate_answer_fn = (
                    lambda question_, retrieval_: generate_graph_answer(
                        question_, retrieval_
                    )
                )
        else:
            from business_graph.graph_answer import is_insufficient_retrieval

        try:
            retrieval = retrieve_fn(q)
        except Exception as exc:
            logger.exception('Graph Agent: retrieval failed | %s', exc)
            return _failure(
                q,
                answer=(
                    'I could not retrieve business-graph data for that question. '
                    'Please try again later.'
                ),
                error=f'retrieval_failed:{type(exc).__name__}',
            )

        if not isinstance(retrieval, dict):
            retrieval = {}

        source = str(retrieval.get('source') or 'neo4j')

        try:
            answer = generate_answer_fn(q, retrieval)
        except Exception as exc:
            logger.exception('Graph Agent: answer generation failed | %s', exc)
            return _failure(
                q,
                retrieval=retrieval,
                answer=(
                    'I retrieved graph context but could not generate a grounded '
                    'answer. Please try again.'
                ),
                error=f'answer_generation_failed:{type(exc).__name__}',
                source=source,
            )

        answer = (answer or '').strip() or INSUFFICIENT_ANSWER

        if is_insufficient_retrieval(retrieval):
            return _failure(
                q,
                retrieval=retrieval,
                answer=answer or INSUFFICIENT_ANSWER,
                error='unsupported_or_empty_graph',
                source=source,
            )

        return _success(
            q,
            retrieval=retrieval,
            answer=answer,
            source=source,
        )
    finally:
        if owned_store is not None:
            try:
                owned_store.close()
            except Exception:
                logger.exception('Graph Agent: failed to close Neo4j store')
