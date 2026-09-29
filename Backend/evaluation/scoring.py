"""
Score RetailAsk pipeline results against the evaluation dataset.

Pure functions only: no LLM, MySQL, or Neo4j access, so they are unit-testable.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / 'eval_dataset.json'
RESULTS_DIR = Path(__file__).resolve().parent / 'results'
LATEST_RESULTS_PATH = RESULTS_DIR / 'latest.json'


def load_dataset(path: Path | str = DEFAULT_DATASET_PATH) -> list[dict[str, Any]]:
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    return list(data.get('cases') or [])


def load_latest_results(path: Path | str = LATEST_RESULTS_PATH) -> dict[str, Any] | None:
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def _normalize_text(text: str) -> str:
    # "64,186.66" and "$64186.66" should both match "64186.66".
    lowered = (text or '').lower()
    return re.sub(r'(?<=\d),(?=\d)', '', lowered)


def missing_keywords(answer: str, keywords: list[str]) -> list[str]:
    normalized = _normalize_text(answer)
    return [kw for kw in keywords or [] if _normalize_text(kw) not in normalized]


def sql_was_executed(result: dict[str, Any]) -> bool:
    sql_result = (result.get('results') or {}).get('sql') or {}
    return bool(sql_result.get('success') and sql_result.get('sql'))


def score_case(
    case: dict[str, Any],
    result: dict[str, Any],
    *,
    routing_only: bool = False,
) -> dict[str, Any]:
    """
    Compare one pipeline result with one eval case.

    `result` is the dict returned by run_supervised_question (or, in routing-only
    mode, any dict with a `route` key).
    """
    expected_routes = [r.lower() for r in case.get('expected_routes') or []]
    actual_route = str(result.get('route') or '').lower()
    route_ok = not expected_routes or actual_route in expected_routes

    checks: dict[str, bool] = {'route': route_ok}
    missing: list[str] = []
    answer = result.get('answer') or ''

    if not routing_only:
        if case.get('expect_refusal'):
            checks['refused'] = not sql_was_executed(result)
        elif case.get('expect_success', True):
            checks['success'] = bool(result.get('success'))

        missing = missing_keywords(answer, case.get('answer_must_include') or [])
        checks['answer'] = not missing

    return {
        'id': case.get('id'),
        'question': case.get('question'),
        'category': case.get('category') or 'uncategorized',
        'source': case.get('source') or 'dataset',
        'expected_routes': expected_routes,
        'actual_route': actual_route,
        'route_reason': (result.get('routing') or {}).get('reason'),
        'checks': checks,
        'missing_keywords': missing,
        'passed': all(checks.values()),
        'answer': answer,
        'error': result.get('error'),
        'notes': case.get('notes'),
    }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def summarize(scored: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(scored)
    passed = sum(1 for s in scored if s['passed'])
    route_ok = sum(1 for s in scored if s['checks'].get('route'))
    answer_scored = [s for s in scored if 'answer' in s['checks']]
    answer_ok = sum(1 for s in answer_scored if s['checks']['answer'])

    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {'total': 0, 'passed': 0})
    for s in scored:
        bucket = by_category[s['category']]
        bucket['total'] += 1
        bucket['passed'] += int(s['passed'])

    return {
        'total': total,
        'passed': passed,
        'pass_rate': _rate(passed, total),
        'route_accuracy': _rate(route_ok, total),
        'answer_accuracy': _rate(answer_ok, len(answer_scored)) if answer_scored else None,
        'by_category': dict(by_category),
        'failed_ids': [s['id'] for s in scored if not s['passed']],
    }
