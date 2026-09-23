#!/usr/bin/env python3
"""
Demo for RetailAsk Graph Agent (Step 4C).

Question → Graph Retrieval → Neo4j → Graph RAG answer.
Independent of Supervisor, SQL Agent, and /query.
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

from agents.graph_agent import run_graph_agent
from business_graph import Neo4jGraphStore
from business_graph.retriever import format_retrieval_report

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)

DEMO_QUESTIONS = [
    'Which products have quality issues?',
    'Which products have negative feedback and returns?',
    'Which brands have products with negative feedback?',
    'Which products have high sales and quality issues?',
]


def main() -> int:
    parser = argparse.ArgumentParser(description='RetailAsk Graph Agent demo')
    parser.add_argument('--question', type=str, default=None)
    args = parser.parse_args()

    questions = [args.question] if args.question else DEMO_QUESTIONS
    store = Neo4jGraphStore.from_env()
    try:
        for question in questions:
            print('=' * 72)
            print(f'Question\n{question}\n')
            print('→ Graph Agent')

            result = run_graph_agent(question, store=store)
            retrieval = result.get('retrieval') or {}
            intent = retrieval.get('intent') or {}

            print('→ Graph retrieval intent')
            print(f'   {json.dumps(intent, default=str)}')
            print()

            print('→ Neo4j retrieval')
            print(f'   source={result.get("source")}')
            print(
                f'   nodes={len(retrieval.get("nodes") or [])} | '
                f'relationships={len(retrieval.get("relationships") or [])} | '
                f'facts={len(retrieval.get("facts") or [])}'
            )
            print()

            print('→ Retrieved graph facts')
            print(format_retrieval_report(retrieval))
            print()

            print('→ Qwen grounded answer')
            print(f'   {result.get("answer")}')
            print(f'   success={result.get("success")}')
            if result.get('error'):
                print(f'   error={result.get("error")}')
            print()
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
