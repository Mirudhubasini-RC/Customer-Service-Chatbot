#!/usr/bin/env python3
"""
Demo for RetailAsk Supervisor Agent (Step 4A).

Routes questions with Qwen; does not execute SQL or Graph RAG.
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

from agents.supervisor import route_question

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)

DEMO_QUESTIONS = [
    ('SQL', 'How much revenue did we make?'),
    ('Graph', 'Which products have negative feedback and returns?'),
    ('General', 'What is customer retention?'),
    ('SQL + Graph', 'Which high-selling products also have negative feedback?'),
]


def main() -> int:
    parser = argparse.ArgumentParser(description='RetailAsk Supervisor demo')
    parser.add_argument('--question', type=str, default=None)
    args = parser.parse_args()

    if args.question:
        items = [('Custom', args.question)]
    else:
        items = DEMO_QUESTIONS

    for label, question in items:
        print('=' * 72)
        print(f'Expected category: {label}')
        print(f'Question: {question}')
        decision = route_question(question)
        print('Supervisor decision:')
        print(json.dumps(decision, indent=2))
        print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
