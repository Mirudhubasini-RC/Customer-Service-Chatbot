#!/usr/bin/env python3
"""
Demo for RetailAsk Graph RAG (Step 3D).

Question → Neo4j graph retrieval → Qwen2.5-Coder grounded answer.
Independent of the main /query SQL pipeline.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / '.env', override=True)

from business_graph import Neo4jGraphStore
from business_graph.graph_answer import run_graph_rag
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
    parser = argparse.ArgumentParser(description='RetailAsk Graph RAG demo')
    parser.add_argument('--question', type=str, default=None)
    args = parser.parse_args()

    store = Neo4jGraphStore.from_env()
    try:
        questions = [args.question] if args.question else DEMO_QUESTIONS
        for question in questions:
            print('=' * 72)
            print(f'Question:\n{question}\n')
            result = run_graph_rag(question, store=store)
            print('Retrieved graph context:')
            print(format_retrieval_report(result['retrieval']))
            print('\nQwen answer (grounded in Neo4j graph context):')
            print(result['answer'])
            print()
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
