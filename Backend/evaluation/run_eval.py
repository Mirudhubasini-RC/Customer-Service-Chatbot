"""
Run the RetailAsk evaluation set against the live pipeline.

Usage (from Backend/, virtualenv active, .env configured):

    python -m evaluation.run_eval                    # full pipeline: route + answer + safety
    python -m evaluation.run_eval --routing-only     # Supervisor routing only (fast, 1 LLM call each)
    python -m evaluation.run_eval --include-feedback # also run disliked questions promoted from the app
    python -m evaluation.run_eval --ids sql-01 graph-01

Results are written to evaluation/results/latest.json (shown in the app's
"Feedback & Eval" view) plus a timestamped copy in evaluation/results/history/.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .scoring import (
    DEFAULT_DATASET_PATH,
    LATEST_RESULTS_PATH,
    RESULTS_DIR,
    load_dataset,
    score_case,
    summarize,
)

logger = logging.getLogger('retail-agent')

PipelineFn = Callable[[str], dict[str, Any]]


def collect_cases(
    *,
    include_feedback: bool = False,
    ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    cases = load_dataset(DEFAULT_DATASET_PATH)
    if include_feedback:
        from feedback_store import feedback_eval_cases

        try:
            cases += feedback_eval_cases()
        except Exception as exc:
            logger.warning('Could not load feedback eval cases | %s', exc)
    if ids:
        wanted = set(ids)
        cases = [c for c in cases if c.get('id') in wanted]
    return cases


def run_eval(
    cases: list[dict[str, Any]],
    *,
    routing_only: bool = False,
    sleep_seconds: float = 0.0,
    pipeline_fn: PipelineFn | None = None,
    on_case: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if pipeline_fn is None:
        if routing_only:
            from agents.supervisor import route_question as pipeline_fn
        else:
            from agents.orchestrator import run_question as pipeline_fn

    started = time.time()
    scored = []
    for index, case in enumerate(cases):
        if index and sleep_seconds:
            time.sleep(sleep_seconds)
        try:
            result = pipeline_fn(case['question'])
        except Exception as exc:
            logger.exception('Eval case crashed | id=%s', case.get('id'))
            result = {'route': 'error', 'success': False, 'error': f'{type(exc).__name__}: {exc}'}
        if routing_only:
            result = {'route': result.get('route'), 'routing': result, 'error': result.get('error')}
        item = score_case(case, result, routing_only=routing_only)
        scored.append(item)
        if on_case:
            on_case(item)

    return {
        'run_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'mode': 'routing_only' if routing_only else 'full',
        'duration_seconds': round(time.time() - started, 1),
        'model': _active_model_label(),
        'orchestrator': 'n/a (supervisor only)' if routing_only else _active_orchestrator(),
        'summary': summarize(scored),
        'cases': scored,
    }


def _active_model_label() -> str:
    try:
        from app import _active_model_label as label

        return label()
    except Exception:
        return 'unknown'


def _active_orchestrator() -> str:
    from agents.orchestrator import active_orchestrator

    return active_orchestrator()


def save_results(report: dict[str, Any]) -> None:
    history_dir = RESULTS_DIR / 'history'
    history_dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(report, indent=2, default=str)
    LATEST_RESULTS_PATH.write_text(body, encoding='utf-8')
    stamp = report['run_at'].replace(':', '').replace('-', '')
    (history_dir / f"{stamp}_{report['mode']}.json").write_text(body, encoding='utf-8')


def _print_case(item: dict[str, Any]) -> None:
    mark = 'PASS' if item['passed'] else 'FAIL'
    failed = [name for name, ok in item['checks'].items() if not ok]
    detail = f"  failed: {', '.join(failed)}" if failed else ''
    if item['missing_keywords']:
        detail += f"  missing: {item['missing_keywords']}"
    print(
        f"[{mark}] {item['id']:<10} route={item['actual_route']:<14} "
        f"expected={'/'.join(item['expected_routes']) or '-':<22}{detail}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run the RetailAsk evaluation set.')
    parser.add_argument('--routing-only', action='store_true', help='Only score Supervisor routing.')
    parser.add_argument('--include-feedback', action='store_true', help='Add questions promoted from user feedback.')
    parser.add_argument('--ids', nargs='*', help='Only run these case ids.')
    parser.add_argument(
        '--sleep',
        type=float,
        default=None,
        help='Seconds between cases for LLM rate limits (default: 1 routing-only, 4 full).',
    )
    args = parser.parse_args(argv)
    if args.sleep is None:
        args.sleep = 1.0 if args.routing_only else 4.0

    cases = collect_cases(include_feedback=args.include_feedback, ids=args.ids)
    if not cases:
        print('No eval cases selected.')
        return 1

    print(f"Running {len(cases)} case(s) | mode={'routing_only' if args.routing_only else 'full'}\n")
    report = run_eval(
        cases,
        routing_only=args.routing_only,
        sleep_seconds=args.sleep,
        on_case=_print_case,
    )
    save_results(report)

    s = report['summary']
    print(
        f"\nPassed {s['passed']}/{s['total']} ({s['pass_rate']:.0%}) | "
        f"route accuracy {s['route_accuracy']:.0%}"
        + (
            f" | answer accuracy {s['answer_accuracy']:.0%}"
            if s['answer_accuracy'] is not None
            else ''
        )
    )
    print(f'Saved to {LATEST_RESULTS_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
