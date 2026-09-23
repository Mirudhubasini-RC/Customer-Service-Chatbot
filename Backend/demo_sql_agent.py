#!/usr/bin/env python3
"""
Demo for RetailAsk SQL Agent (Step 4B).

Question → Schema RAG → Qwen SQL → safety → MySQL → NL answer.
Independent of Supervisor and /query.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / '.env', override=True)

from agents.sql_agent import run_sql_agent
from app import is_safe_select

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)

DEMO_QUESTIONS = [
    'How much revenue did we make?',
    'Which products sold the most?',
    'What is the average sale value?',
    'What was the revenue for August 2024?',
]


def _print_schema(schema_context: dict) -> None:
    tables = schema_context.get('expanded_tables') or schema_context.get('retrieved_tables') or []
    scores = schema_context.get('scores') or {}
    print('→ Retrieved schema (Schema RAG)')
    print(f'   tables: {", ".join(tables) if tables else "(none)"}')
    if scores:
        print(f'   scores: {json.dumps(scores)}')
    context_text = schema_context.get('schema_context') or ''
    if context_text:
        preview = context_text if len(context_text) <= 600 else context_text[:600] + '...'
        print('   context preview:')
        for line in preview.splitlines():
            print(f'     {line}')


def main() -> int:
    parser = argparse.ArgumentParser(description='RetailAsk SQL Agent demo')
    parser.add_argument('--question', type=str, default=None)
    args = parser.parse_args()

    questions = [args.question] if args.question else DEMO_QUESTIONS

    for question in questions:
        print('=' * 72)
        print(f'Question\n{question}\n')

        result = run_sql_agent(question)

        _print_schema(result.get('schema_context') or {})
        print()

        sql = result.get('sql')
        print('→ Generated SQL')
        print(f'   {sql if sql else "(none)"}')
        print()

        if sql:
            safe = is_safe_select(sql)
            print('→ Safety validation')
            print(f'   {"PASS (SELECT-only)" if safe else "REJECTED (unsafe)"}')
        else:
            print('→ Safety validation')
            print('   skipped (no SQL to validate)')
        print()

        print('→ Query result')
        if result.get('error') == 'unsafe_sql_rejected':
            print('   (not executed — unsafe SQL)')
        elif result.get('error') and result.get('error', '').startswith('sql_execution'):
            print(f'   execution error: {result["error"]}')
        else:
            rows = result.get('rows') or []
            print(f'   {len(rows)} row(s)')
            if rows:
                print(f'   preview: {json.dumps(rows[:5], default=str)}')
        print()

        print('→ Final answer')
        print(f'   {result.get("answer")}')
        print(f'   success={result.get("success")}')
        if result.get('error'):
            print(f'   error={result.get("error")}')
        print()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
