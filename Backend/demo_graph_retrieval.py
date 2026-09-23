#!/usr/bin/env python3
"""
Demo for RetailAsk Business Graph Retrieval (Step 3C).

Question → GraphRetriever → Neo4j Aura → graph context (no Qwen).
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
from business_graph.retriever import GraphRetriever, format_retrieval_report

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
    parser = argparse.ArgumentParser(description='RetailAsk graph retrieval demo')
    parser.add_argument(
        '--question',
        type=str,
        default=None,
        help='Run a single question instead of the demo set',
    )
    args = parser.parse_args()

    store = Neo4jGraphStore.from_env()
    try:
        retriever = GraphRetriever(store)
        questions = [args.question] if args.question else DEMO_QUESTIONS
        for question in questions:
            print('=' * 72)
            context = retriever.retrieve(question)
            print(format_retrieval_report(context))
            print()
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
