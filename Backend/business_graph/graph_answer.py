"""
Graph RAG answer generation (Step 3D).

Takes Neo4j graph retrieval context + user question → grounded Qwen answer.
Does not run Schema RAG / SQL. Does not implement agents.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

logger = logging.getLogger('retail-agent')

LLMCall = Callable[..., str]

GRAPH_ANSWER_SYSTEM_PROMPT = (
    'You are RetailAsk, a retail analytics assistant for store owners. '
    'Answer ONLY using the supplied Neo4j business-graph context. '
    'Do not invent products, brands, categories, issues, relationships, '
    'numbers, causes, or business facts that are not present in the context. '
    'If the context is empty or insufficient, say clearly that the available '
    'graph data is insufficient to answer. '
    'When useful, briefly explain the relevant relationships '
    '(for example Product → Feedback → Issue, or Brand → Product → Feedback). '
    'Do not generate SQL. '
    'Do not treat guessed or inferred links as confirmed graph relationships. '
    'Keep the answer concise (2–6 short sentences or a short bullet list).'
)


def format_graph_context_for_prompt(retrieval: dict[str, Any]) -> str:
    """Compress normalized retrieval into text for the LLM."""
    facts = retrieval.get('facts') or []
    relationships = retrieval.get('relationships') or []
    nodes = retrieval.get('nodes') or []
    intent = retrieval.get('intent') or {}

    # Prefer human-readable facts; include compact node/rel summaries as backup.
    payload = {
        'intent': intent,
        'facts': facts[:40],
        'relationship_triple_count': len(relationships),
        'relationship_types': sorted({r.get('type') for r in relationships if r.get('type')}),
        'node_labels': sorted({n.get('label') for n in nodes if n.get('label')}),
        'sample_nodes': [
            {
                'label': n.get('label'),
                'key': n.get('key'),
                'name': (
                    n.get('product_name')
                    or n.get('brand_name')
                    or n.get('category_name')
                    or n.get('issue_name')
                ),
            }
            for n in nodes[:25]
        ],
    }
    return json.dumps(payload, ensure_ascii=True, default=str)


def is_insufficient_retrieval(retrieval: dict[str, Any] | None) -> bool:
    if not retrieval:
        return True
    facts = retrieval.get('facts') or []
    nodes = retrieval.get('nodes') or []
    if not facts and not nodes:
        return True
    if len(facts) == 1 and facts[0].get('type') in ('unsupported',):
        return True
    return False


def build_graph_answer_messages(question: str, retrieval: dict[str, Any]) -> list[dict[str, str]]:
    context_text = format_graph_context_for_prompt(retrieval)
    user_content = (
        f'Question: {question}\n\n'
        f'Neo4j graph context (JSON):\n{context_text}\n\n'
        'Write the grounded natural-language answer now.'
    )
    return [
        {'role': 'system', 'content': GRAPH_ANSWER_SYSTEM_PROMPT},
        {'role': 'user', 'content': user_content},
    ]


def generate_graph_answer(
    question: str,
    retrieval: dict[str, Any],
    *,
    llm_call: LLMCall | None = None,
    max_tokens: int = 280,
    temperature: float = 0.2,
) -> str:
    """
    Call Qwen with a grounded prompt built from graph retrieval context.
    """
    if is_insufficient_retrieval(retrieval):
        return (
            'The available Neo4j graph data is insufficient to answer this question. '
            'No matching business-graph facts were retrieved.'
        )

    if llm_call is None:
        from app import call_llm

        llm_call = call_llm

    messages = build_graph_answer_messages(question, retrieval)
    logger.info(
        'Graph RAG answer start | question=%s | facts=%s | nodes=%s',
        question,
        len(retrieval.get('facts') or []),
        len(retrieval.get('nodes') or []),
    )
    answer = llm_call(messages, max_tokens=max_tokens, temperature=temperature)
    logger.info('Graph RAG answer done | chars=%s', len(answer or ''))
    return (answer or '').strip()


def run_graph_rag(
    question: str,
    *,
    retriever: Any | None = None,
    store: Any | None = None,
    llm_call: LLMCall | None = None,
    retrieval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Full Step 3D pipeline for one question:

      question → GraphRetriever → Neo4j context → Qwen → answer

    Pass `retrieval` to skip Neo4j (tests). Pass `llm_call` to mock Qwen.
    """
    if retrieval is None:
        if retriever is None:
            if store is None:
                raise ValueError('Provide retriever, store, or retrieval')
            from .retriever import GraphRetriever

            retriever = GraphRetriever(store)
        retrieval = retriever.retrieve(question)

    answer = generate_graph_answer(question, retrieval, llm_call=llm_call)
    return {
        'question': question,
        'source': 'neo4j',
        'retrieval': retrieval,
        'answer': answer,
    }
