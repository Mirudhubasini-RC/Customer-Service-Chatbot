"""
Supervisor Agent (Step 4A) — routing only.

Uses Qwen2.5-Coder via call_llm() to choose:
  sql | graph | general | sql_and_graph

Does not execute SQL, Graph RAG, or any downstream agent.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

logger = logging.getLogger('retail-agent')

LLMCall = Callable[..., str]

VALID_ROUTES = frozenset({'sql', 'graph', 'general', 'sql_and_graph'})

SUPERVISOR_SYSTEM_PROMPT = """
You are the RetailAsk Supervisor. Your only job is to route a retail-owner question
to exactly one capability. Do NOT answer the question. Do NOT write SQL. Do NOT
invent database tables, columns, products, or graph relationships.

Available routes:

1) "sql"
   Use for structured analytics against the transactional MySQL database:
   revenue, totals, averages, rankings, quantities, prices, date-based sales,
   top products by sales/revenue, and similar aggregate/metric questions.

2) "graph"
   Use for relationship / traversal questions over the Neo4j business graph:
   products linked to negative feedback and returns, brands with negative
   feedback, products connected to issues, products with both sales signals
   and feedback/issues when the emphasis is on graph relationships.

3) "general"
   Use when neither MySQL sales metrics nor the business graph are needed
   (definitions, advice, conceptual questions, chit-chat).

4) "sql_and_graph"
   Use ONLY when the question genuinely needs BOTH structured SQL metrics
   AND graph relationships in one answer (for example high-selling products
   that also have negative feedback). Prefer a single route ("sql" or "graph")
   when one is enough.

Return JSON ONLY with this exact shape (no markdown fences, no extra keys):
{"route":"sql|graph|general|sql_and_graph","reason":"short explanation","question":"<original question unchanged>"}
""".strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = text.strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', cleaned, re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def _fallback_route(question: str, reason: str) -> dict[str, str]:
    """Safe default when the LLM output cannot be trusted."""
    return {
        'route': 'general',
        'reason': reason,
        'question': question,
    }


def _normalize_decision(question: str, payload: dict[str, Any] | None) -> dict[str, str]:
    if not payload:
        return _fallback_route(
            question,
            'Invalid or missing JSON from supervisor LLM; defaulting to general.',
        )

    route = str(payload.get('route') or '').strip().lower()
    reason = str(payload.get('reason') or '').strip() or 'No reason provided.'
    # Always preserve the caller's original question (ignore model mutations).
    if route not in VALID_ROUTES:
        return _fallback_route(
            question,
            f'Invalid route {route!r} from supervisor LLM; defaulting to general.',
        )
    return {
        'route': route,
        'reason': reason,
        'question': question,
    }


def route_question(
    question: str,
    *,
    llm_call: LLMCall | None = None,
    max_tokens: int = 120,
    temperature: float = 0.0,
) -> dict[str, str]:
    """
    Ask Qwen which downstream capability should handle `question`.

    Returns:
      {"route": "...", "reason": "...", "question": "<original>"}
    """
    q = (question or '').strip()
    if not q:
        return _fallback_route('', 'Empty question; defaulting to general.')

    if llm_call is None:
        from app import call_llm

        llm_call = call_llm

    messages = [
        {'role': 'system', 'content': SUPERVISOR_SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': (
                f'Question: {q}\n\n'
                'Return JSON only with keys route, reason, question.'
            ),
        },
    ]

    try:
        raw = llm_call(messages, max_tokens=max_tokens, temperature=temperature)
    except Exception as exc:
        logger.exception('Supervisor LLM call failed | %s', exc)
        return _fallback_route(
            q,
            f'Supervisor LLM call failed ({type(exc).__name__}); defaulting to general.',
        )

    logger.info('Supervisor raw LLM output | %s', raw)
    payload = _extract_json_object(raw)
    decision = _normalize_decision(q, payload)
    logger.info(
        'Supervisor decision | route=%s | reason=%s',
        decision['route'],
        decision['reason'],
    )
    return decision
