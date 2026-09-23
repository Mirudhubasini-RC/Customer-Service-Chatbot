"""
SQL Agent (Step 4B) — structured retail analytics via Schema RAG + MySQL.

Orchestrates existing capabilities; does not rewrite the SQL pipeline.
Independent of the Supervisor (not wired yet).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger('retail-agent')

GenerateSqlFn = Callable[[str], tuple[str | None, dict[str, Any]]]
SafeSelectFn = Callable[[str | None], bool]
ExecuteSqlFn = Callable[[str], list[dict[str, Any]]]
ExplainRowsFn = Callable[[str, str, list[dict[str, Any]]], str]

EMPTY_ROWS_ANSWER = (
    'I ran that against the database, but no matching rows were found.'
)


def _failure(
    question: str,
    *,
    schema_context: dict[str, Any] | None = None,
    sql: str | None = None,
    rows: list[dict[str, Any]] | None = None,
    answer: str,
    error: str,
) -> dict[str, Any]:
    return {
        'agent': 'sql',
        'question': question,
        'schema_context': schema_context or {},
        'sql': sql,
        'rows': rows if rows is not None else [],
        'answer': answer,
        'success': False,
        'error': error,
    }


def _success(
    question: str,
    *,
    schema_context: dict[str, Any],
    sql: str,
    rows: list[dict[str, Any]],
    answer: str,
) -> dict[str, Any]:
    return {
        'agent': 'sql',
        'question': question,
        'schema_context': schema_context,
        'sql': sql,
        'rows': rows,
        'answer': answer,
        'success': True,
        'error': None,
    }


def run_sql_agent(
    question: str,
    *,
    generate_sql_fn: GenerateSqlFn | None = None,
    is_safe_select_fn: SafeSelectFn | None = None,
    execute_sql_fn: ExecuteSqlFn | None = None,
    explain_rows_fn: ExplainRowsFn | None = None,
) -> dict[str, Any]:
    """
    Run the SQL Agent pipeline for a retail analytics question.

    Flow: Schema RAG → Qwen SQL → safety validation → MySQL → NL answer.

    Injectable callables are for unit tests; production uses app.py helpers.
    """
    q = (question or '').strip()
    if not q:
        return _failure(
            '',
            answer='Please ask a retail analytics question.',
            error='empty_question',
        )

    # Lazy imports keep the agent importable in tests without loading Flask/app eagerly
    # when all dependencies are injected.
    if generate_sql_fn is None or is_safe_select_fn is None or execute_sql_fn is None or explain_rows_fn is None:
        from app import (
            execute_sql_query,
            explain_rows,
            generate_sql,
            is_safe_select,
        )

        if generate_sql_fn is None:
            generate_sql_fn = generate_sql
        if is_safe_select_fn is None:
            is_safe_select_fn = is_safe_select
        if execute_sql_fn is None:
            execute_sql_fn = execute_sql_query
        if explain_rows_fn is None:
            explain_rows_fn = explain_rows

    schema_context: dict[str, Any] = {}
    sql: str | None = None

    try:
        sql, schema_context = generate_sql_fn(q)
    except Exception as exc:
        logger.exception('SQL Agent: SQL generation failed | %s', exc)
        return _failure(
            q,
            answer=(
                'I could not generate a safe SQL query for that question. '
                'Please try rephrasing it.'
            ),
            error=f'sql_generation_failed:{type(exc).__name__}',
        )

    # Schema RAG is performed inside generate_sql(); surface its metadata.
    if not isinstance(schema_context, dict):
        schema_context = {}

    if not sql:
        return _failure(
            q,
            schema_context=schema_context,
            sql=None,
            answer=(
                'I could not produce a valid SELECT query for that question '
                'from the retrieved schema.'
            ),
            error='sql_generation_unsupported_or_invalid',
        )

    # Explicit safety gate (generate_sql already filters; re-check for injectables).
    if not is_safe_select_fn(sql):
        logger.warning('SQL Agent: rejected unsafe SQL | %s', sql)
        return _failure(
            q,
            schema_context=schema_context,
            sql=sql,
            answer=(
                'The generated SQL was rejected by the safety validator '
                'and was not executed.'
            ),
            error='unsafe_sql_rejected',
        )

    try:
        rows = execute_sql_fn(sql)
    except Exception as exc:
        logger.exception('SQL Agent: MySQL execution failed | %s', exc)
        return _failure(
            q,
            schema_context=schema_context,
            sql=sql,
            answer='The SQL query failed when run against the database.',
            error=f'sql_execution_failed:{type(exc).__name__}',
        )

    if not rows:
        return _success(
            q,
            schema_context=schema_context,
            sql=sql,
            rows=[],
            answer=EMPTY_ROWS_ANSWER,
        )

    try:
        answer = explain_rows_fn(q, sql, rows)
    except Exception as exc:
        logger.exception('SQL Agent: explain failed, using row preview | %s', exc)
        preview = rows[:10]
        answer = (
            f'Here are the results from the database ({len(rows)} row(s)): '
            f'{preview}'
        )

    return _success(
        q,
        schema_context=schema_context,
        sql=sql,
        rows=rows,
        answer=answer,
    )
