#!/usr/bin/env python3
"""
Demo for RetailAsk Supervisor + Agent Orchestration (Step 4D).

Routes via Supervisor, then runs SQL and/or Graph agents.
Same path as Flask /query (app.answer_query → run_question → LangGraph by default).

    python demo_orchestrator.py --mermaid   # print the LangGraph workflow diagram
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

from agents.orchestrator import active_orchestrator, run_question

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


def _summarize_results(route: str, results: dict) -> None:
    if route == 'sql':
        sql = results.get('sql') or {}
        print(f"   SQL success={sql.get('success')} | sql={sql.get('sql')}")
        rows = sql.get('rows') or []
        print(f'   rows={len(rows)} preview={json.dumps(rows[:3], default=str)}')
    elif route == 'graph':
        graph = results.get('graph') or {}
        retrieval = graph.get('retrieval') or {}
        print(
            f"   Graph success={graph.get('success')} | "
            f"facts={len(retrieval.get('facts') or [])} | "
            f"intent={(retrieval.get('intent') or {}).get('intent_type')}"
        )
    elif route == 'general':
        print(f"   general={json.dumps(results.get('general'), default=str)}")
    elif route == 'sql_and_graph':
        sql = results.get('sql') or {}
        graph = results.get('graph') or {}
        synth = results.get('synthesis') or {}
        print(f"   SQL success={sql.get('success')} | sql={sql.get('sql')}")
        print(
            f"   Graph success={graph.get('success')} | "
            f"facts={len((graph.get('retrieval') or {}).get('facts') or [])}"
        )
        print(f"   Synthesis success={synth.get('success')} error={synth.get('error')}")


def main() -> int:
    parser = argparse.ArgumentParser(description='RetailAsk orchestrator demo')
    parser.add_argument('--question', type=str, default=None)
    parser.add_argument('--mermaid', action='store_true', help='Print the LangGraph diagram and exit.')
    args = parser.parse_args()

    if args.mermaid:
        from agents.langgraph_orchestrator import retailask_graph_mermaid

        print(retailask_graph_mermaid())
        return 0

    print(f'Orchestrator: {active_orchestrator()}')
    items = [('Custom', args.question)] if args.question else DEMO_QUESTIONS

    for label, question in items:
        print('=' * 72)
        print(f'Expected category: {label}')
        print(f'Question: {question}\n')

        result = run_question(question)

        print(f"→ Supervisor route: {result.get('route')}")
        routing = result.get('routing') or {}
        if routing.get('reason'):
            print(f"   reason: {routing.get('reason')}")
        print()

        print('→ Agent results')
        _summarize_results(result.get('route') or '', result.get('results') or {})
        print()

        print('→ Final answer')
        print(f"   {result.get('answer')}")
        print(f"   success={result.get('success')}")
        if result.get('error'):
            print(f"   error={result.get('error')}")
        print()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
