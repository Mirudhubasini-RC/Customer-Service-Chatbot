#!/usr/bin/env python3
"""
Demo / test for RetailAsk Schema RAG (Step 2).

Prints retrieved schema tables for sample retail-owner questions.
Does not call Qwen or MySQL unless --with-sql is passed.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure Backend/ is on sys.path when run as a script
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schema_rag import SchemaRAG

DEMO_QUESTIONS = [
    'Which products have the highest sales?',
    'Which products have quality issues?',
    'Which brands generate the most sales?',
    'Which products have negative feedback and returns?',
    'Which category has the most sales?',
]


def main() -> int:
    parser = argparse.ArgumentParser(description='RetailAsk Schema RAG demo')
    parser.add_argument(
        '--with-sql',
        action='store_true',
        help='Also run generate_sql() (requires HUGGINGFACE_API_KEY / .env)',
    )
    parser.add_argument('--top-k', type=int, default=3, help='Semantic top-k tables')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
    )

    rag = SchemaRAG(top_k=args.top_k)
    print('=' * 72)
    print('RetailAsk Schema RAG demo')
    print(f'Embedding model: {rag.model_name}')
    print(f'Docs: {rag.docs_path}')
    print('=' * 72)

    generate_sql = None
    if args.with_sql:
        from dotenv import load_dotenv

        load_dotenv(BACKEND_DIR / '.env', override=True)
        from app import generate_sql as _generate_sql

        generate_sql = _generate_sql

    for question in DEMO_QUESTIONS:
        print('\n' + '-' * 72)
        print(f'Question: {question}')
        result = rag.retrieve(question, top_k=args.top_k)
        print('Semantic hits (table=score):')
        for table, score in result['scores'].items():
            print(f'  - {table}: {score}')
        print(f"Expanded tables (incl. FK): {', '.join(result['expanded_tables'])}")

        if generate_sql is not None:
            sql, meta = generate_sql(question)
            print(f'Qwen SQL: {sql}')
            print(f"Schema tables used: {', '.join(meta.get('expanded_tables') or [])}")

    print('\nDone.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
