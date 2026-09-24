"""
Supervisor + Agent Orchestration (Step 4D).

Routes via the Supervisor, then executes SQL Agent / Graph Agent as needed.
Does not modify agent internals. Does not wire /query. No A2A yet.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

logger = logging.getLogger('retail-agent')

RouteFn = Callable[[str], dict[str, Any]]
SqlAgentFn = Callable[[str], dict[str, Any]]
GraphAgentFn = Callable[[str], dict[str, Any]]
LLMCall = Callable[..., str]

GENERAL_ANSWER = (
    'This question looks like a general / non-database request. '
    'RetailAsk has not run SQL or business-graph retrieval for it. '
    'A dedicated General Agent is not wired yet — ask about sales metrics '
    '(SQL) or product–feedback–issue relationships (graph) for data-backed answers.'
)

SYNTHESIS_SYSTEM_PROMPT = """
You are RetailAsk's final answer synthesizer for questions that need BOTH
structured MySQL/SQL analytics and Neo4j business-graph relationships.

You receive:
1) the original user question
2) the SQL Agent result JSON (metrics / query rows / SQL-derived answer)
3) the Graph Agent result JSON (graph facts / grounded graph answer)

Rules:
- Answer ONLY using facts present in those two results.
- Do NOT invent products, numbers, relationships, or causes.
- Do NOT generate SQL or Cypher.
- Do NOT call tools.
- When useful, clearly distinguish SQL-derived facts from graph-derived facts.
- If either side failed or is insufficient, say so explicitly and answer only
  from what is available — do not pretend both sources succeeded.
- If neither side has usable information, say the available data is insufficient.
- Keep the answer concise (3–8 short sentences or a short bullet list).
""".strip()


def _compact_agent_payload(result: dict[str, Any] | None, kind: str) -> dict[str, Any]:
    """Shrink agent output for the synthesis prompt (avoid huge row dumps)."""
    if not result:
        return {'agent': kind, 'success': False, 'error': 'missing_result', 'answer': None}

    if kind == 'sql':
        rows = result.get('rows') or []
        return {
            'agent': 'sql',
            'success': bool(result.get('success')),
            'error': result.get('error'),
            'sql': result.get('sql'),
            'row_count': len(rows),
            'rows_preview': rows[:15],
            'answer': result.get('answer'),
        }

    retrieval = result.get('retrieval') or {}
    facts = retrieval.get('facts') or []
    return {
        'agent': 'graph',
        'success': bool(result.get('success')),
        'error': result.get('error'),
        'source': result.get('source') or 'neo4j',
        'intent': retrieval.get('intent'),
        'fact_count': len(facts),
        'facts_preview': facts[:25],
        'answer': result.get('answer'),
    }


def _build_synthesis_messages(
    question: str,
    sql_result: dict[str, Any] | None,
    graph_result: dict[str, Any] | None,
) -> list[dict[str, str]]:
    payload = {
        'question': question,
        'sql_agent': _compact_agent_payload(sql_result, 'sql'),
        'graph_agent': _compact_agent_payload(graph_result, 'graph'),
    }
    user_content = (
        'Synthesize ONE final grounded answer from the SQL and Graph agent results.\n\n'
        f'{json.dumps(payload, ensure_ascii=True, default=str)}'
    )
    return [
        {'role': 'system', 'content': SYNTHESIS_SYSTEM_PROMPT},
        {'role': 'user', 'content': user_content},
    ]


def synthesize_sql_and_graph_answer(
    question: str,
    sql_result: dict[str, Any] | None,
    graph_result: dict[str, Any] | None,
    *,
    llm_call: LLMCall | None = None,
    max_tokens: int = 320,
    temperature: float = 0.2,
) -> str:
    """Call Qwen to merge SQL + Graph agent results into one answer."""
    if llm_call is None:
        from app import call_llm

        llm_call = call_llm

    messages = _build_synthesis_messages(question, sql_result, graph_result)
    logger.info('Orchestrator synthesis start | question=%s', question)
    answer = llm_call(messages, max_tokens=max_tokens, temperature=temperature)
    logger.info('Orchestrator synthesis done | chars=%s', len(answer or ''))
    return (answer or '').strip()


def _safe_run_agent(
    label: str,
    fn: Callable[..., dict[str, Any]],
    question: str,
    **agent_kwargs: Any,
) -> dict[str, Any]:
    try:
        try:
            result = fn(question, **agent_kwargs) if agent_kwargs else fn(question)
        except TypeError:
            # Injected test doubles may only accept the question positional.
            result = fn(question)
        if isinstance(result, dict):
            return result
        return {
            'agent': label,
            'question': question,
            'success': False,
            'error': 'invalid_agent_result',
            'answer': f'The {label} agent returned an unexpected result.',
        }
    except Exception as exc:
        logger.exception('Orchestrator: %s agent crashed | %s', label, exc)
        return {
            'agent': label,
            'question': question,
            'success': False,
            'error': f'agent_exception:{type(exc).__name__}',
            'answer': f'The {label} agent failed unexpectedly.',
        }


def run_supervised_question(
    question: str,
    *,
    route_fn: RouteFn | None = None,
    sql_agent_fn: SqlAgentFn | None = None,
    graph_agent_fn: GraphAgentFn | None = None,
    llm_call: LLMCall | None = None,
    synthesize_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """
    Supervisor → route → execute SQL and/or Graph agents → final answer.

    Injectable callables are for unit tests.
    """
    q = (question or '').strip()
    if not q:
        return {
            'question': '',
            'route': 'general',
            'routing': {'route': 'general', 'reason': 'Empty question.', 'question': ''},
            'results': {'general': {'handled': False, 'reason': 'empty_question'}},
            'answer': 'Please ask a retail analytics question.',
            'success': False,
            'error': 'empty_question',
        }

    if route_fn is None:
        from .supervisor import route_question

        route_fn = route_question
    if sql_agent_fn is None:
        from .sql_agent import run_sql_agent

        sql_agent_fn = run_sql_agent
    if graph_agent_fn is None:
        from .graph_agent import run_graph_agent

        graph_agent_fn = run_graph_agent
    if synthesize_fn is None:
        synthesize_fn = synthesize_sql_and_graph_answer

    try:
        routing = route_fn(q)
    except Exception as exc:
        logger.exception('Orchestrator: supervisor routing failed | %s', exc)
        routing = {
            'route': 'general',
            'reason': f'Supervisor routing failed ({type(exc).__name__}); defaulting to general.',
            'question': q,
        }

    if not isinstance(routing, dict):
        routing = {
            'route': 'general',
            'reason': 'Malformed supervisor response; defaulting to general.',
            'question': q,
        }

    route = str(routing.get('route') or 'general').strip().lower()
    if route not in {'sql', 'graph', 'general', 'sql_and_graph'}:
        routing = {
            **routing,
            'route': 'general',
            'reason': f'Invalid route {route!r}; defaulting to general.',
            'question': q,
        }
        route = 'general'

    logger.info('Orchestrator route | %s | reason=%s', route, routing.get('reason'))

    # --- general ---
    if route == 'general':
        return {
            'question': q,
            'route': 'general',
            'routing': routing,
            'results': {
                'general': {
                    'handled': False,
                    'reason': 'general_agent_not_implemented',
                    'message': GENERAL_ANSWER,
                }
            },
            'answer': GENERAL_ANSWER,
            'success': True,
            'error': None,
        }

    # --- sql only ---
    if route == 'sql':
        sql_result = _safe_run_agent('sql', sql_agent_fn, q)
        return {
            'question': q,
            'route': 'sql',
            'routing': routing,
            'results': {'sql': sql_result},
            'answer': sql_result.get('answer') or '',
            'success': bool(sql_result.get('success')),
            'error': sql_result.get('error'),
        }

    # --- graph only ---
    if route == 'graph':
        graph_result = _safe_run_agent('graph', graph_agent_fn, q)
        return {
            'question': q,
            'route': 'graph',
            'routing': routing,
            'results': {'graph': graph_result},
            'answer': graph_result.get('answer') or '',
            'success': bool(graph_result.get('success')),
            'error': graph_result.get('error'),
        }

    # --- sql_and_graph ---
    # Skip SQL explain_rows LLM; synthesis uses raw rows (+ graph answer).
    sql_result = _safe_run_agent('sql', sql_agent_fn, q, explain_rows=False)
    graph_result = _safe_run_agent('graph', graph_agent_fn, q)
    sql_ok = bool(sql_result.get('success'))
    graph_ok = bool(graph_result.get('success'))

    synthesis_error = None
    try:
        answer = synthesize_fn(
            q,
            sql_result,
            graph_result,
            llm_call=llm_call,
        )
        if not answer:
            raise RuntimeError('empty_synthesis')
    except TypeError:
        # Allow synthesize_fn mocks that only take (question, sql, graph).
        try:
            answer = synthesize_fn(q, sql_result, graph_result)
            if not answer:
                raise RuntimeError('empty_synthesis')
        except Exception as exc:
            logger.exception('Orchestrator: synthesis failed | %s', exc)
            answer = _fallback_partial_answer(sql_result, graph_result)
            synthesis_error = f'synthesis_failed:{type(exc).__name__}'
    except Exception as exc:
        logger.exception('Orchestrator: synthesis failed | %s', exc)
        answer = _fallback_partial_answer(sql_result, graph_result)
        synthesis_error = f'synthesis_failed:{type(exc).__name__}'

    if sql_ok and graph_ok and not synthesis_error:
        overall_success = True
        error = None
    elif sql_ok or graph_ok:
        overall_success = False
        parts = []
        if not sql_ok:
            parts.append(f"sql:{sql_result.get('error') or 'failed'}")
        if not graph_ok:
            parts.append(f"graph:{graph_result.get('error') or 'failed'}")
        if synthesis_error:
            parts.append(synthesis_error)
        error = 'partial_sql_and_graph:' + ','.join(parts)
    else:
        overall_success = False
        error = synthesis_error or 'sql_and_graph_both_failed'

    return {
        'question': q,
        'route': 'sql_and_graph',
        'routing': routing,
        'results': {
            'sql': sql_result,
            'graph': graph_result,
            'synthesis': {
                'success': synthesis_error is None and bool(answer),
                'error': synthesis_error,
            },
        },
        'answer': answer,
        'success': overall_success,
        'error': error,
    }


def _fallback_partial_answer(
    sql_result: dict[str, Any] | None,
    graph_result: dict[str, Any] | None,
) -> str:
    bits = [
        'I could not fully synthesize SQL and graph results. '
        'Here is what each source returned:'
    ]
    if sql_result:
        bits.append(
            f"- SQL ({'ok' if sql_result.get('success') else 'failed'}): "
            f"{sql_result.get('answer') or sql_result.get('error') or 'no answer'}"
        )
    if graph_result:
        bits.append(
            f"- Graph ({'ok' if graph_result.get('success') else 'failed'}): "
            f"{graph_result.get('answer') or graph_result.get('error') or 'no answer'}"
        )
    return '\n'.join(bits)
