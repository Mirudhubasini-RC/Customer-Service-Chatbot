"""Unit tests for the evaluation dataset, scoring, and runner. No LLM or DB access."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from evaluation.run_eval import run_eval
from evaluation.scoring import load_dataset, missing_keywords, score_case, summarize

VALID_ROUTES = {'sql', 'graph', 'general', 'sql_and_graph'}


def _result(route='sql', answer='', success=True, sql=None, sql_success=False):
    return {
        'route': route,
        'routing': {'route': route, 'reason': 'test'},
        'answer': answer,
        'success': success,
        'error': None,
        'results': {'sql': {'sql': sql, 'success': sql_success}} if sql or sql_success else {},
    }


class DatasetTests(unittest.TestCase):
    def test_dataset_is_well_formed(self):
        cases = load_dataset()
        self.assertGreaterEqual(len(cases), 20)
        ids = [c['id'] for c in cases]
        self.assertEqual(len(ids), len(set(ids)), 'case ids must be unique')
        for case in cases:
            self.assertTrue(case['question'].strip(), case['id'])
            self.assertTrue(case['expected_routes'], case['id'])
            self.assertTrue(set(case['expected_routes']) <= VALID_ROUTES, case['id'])

    def test_dataset_covers_every_route_and_safety(self):
        cases = load_dataset()
        routes = {r for c in cases for r in c['expected_routes']}
        self.assertEqual(routes, VALID_ROUTES)
        self.assertTrue(any(c.get('expect_refusal') for c in cases))


class ScoringTests(unittest.TestCase):
    def test_numbers_match_with_thousands_separators(self):
        self.assertEqual(missing_keywords('Revenue was $64,186.66.', ['64186.66']), [])

    def test_keywords_are_case_insensitive(self):
        self.assertEqual(missing_keywords('the MOUSE sold most', ['Mouse']), [])
        self.assertEqual(missing_keywords('Laptop only', ['Laptop', 'Mouse']), ['Mouse'])

    def test_full_pass(self):
        case = {
            'id': 'sql-01',
            'expected_routes': ['sql'],
            'answer_must_include': ['64186.66'],
        }
        scored = score_case(case, _result('sql', 'Total revenue is 64,186.66'))
        self.assertTrue(scored['passed'])
        self.assertEqual(scored['checks'], {'route': True, 'success': True, 'answer': True})

    def test_wrong_route_fails(self):
        case = {'id': 'g', 'expected_routes': ['graph'], 'answer_must_include': []}
        scored = score_case(case, _result('sql'))
        self.assertFalse(scored['passed'])
        self.assertFalse(scored['checks']['route'])

    def test_missing_keyword_fails(self):
        case = {'id': 'g', 'expected_routes': ['graph'], 'answer_must_include': ['Laptop']}
        scored = score_case(case, _result('graph', 'Headphones have issues'))
        self.assertFalse(scored['passed'])
        self.assertEqual(scored['missing_keywords'], ['Laptop'])

    def test_refusal_passes_when_no_sql_ran(self):
        case = {'id': 's', 'expected_routes': ['sql', 'general'], 'expect_refusal': True}
        scored = score_case(case, _result('sql', 'Rejected', success=False, sql=None))
        self.assertTrue(scored['passed'])

    def test_refusal_fails_when_sql_executed(self):
        case = {'id': 's', 'expected_routes': ['sql'], 'expect_refusal': True}
        result = _result('sql', 'Done', sql='SELECT * FROM sales', sql_success=True)
        self.assertFalse(score_case(case, result)['passed'])

    def test_routing_only_ignores_answer(self):
        case = {'id': 'x', 'expected_routes': ['sql'], 'answer_must_include': ['nope']}
        scored = score_case(case, {'route': 'sql'}, routing_only=True)
        self.assertTrue(scored['passed'])
        self.assertEqual(scored['checks'], {'route': True})

    def test_summary(self):
        scored = [
            score_case({'id': 'a', 'category': 'm', 'expected_routes': ['sql']}, _result('sql')),
            score_case({'id': 'b', 'category': 'm', 'expected_routes': ['graph']}, _result('sql')),
        ]
        summary = summarize(scored)
        self.assertEqual(summary['total'], 2)
        self.assertEqual(summary['passed'], 1)
        self.assertEqual(summary['pass_rate'], 0.5)
        self.assertEqual(summary['route_accuracy'], 0.5)
        self.assertEqual(summary['failed_ids'], ['b'])
        self.assertEqual(summary['by_category']['m'], {'total': 2, 'passed': 1})


class RunnerTests(unittest.TestCase):
    def test_runner_scores_each_case_and_survives_crashes(self):
        cases = [
            {'id': 'ok', 'question': 'revenue?', 'expected_routes': ['sql']},
            {'id': 'boom', 'question': 'crash', 'expected_routes': ['graph']},
        ]

        def pipeline(question):
            if question == 'crash':
                raise RuntimeError('llm down')
            return {'route': 'sql', 'reason': 'metrics'}

        report = run_eval(cases, routing_only=True, pipeline_fn=pipeline)
        self.assertEqual(report['mode'], 'routing_only')
        self.assertEqual(report['summary']['passed'], 1)
        self.assertEqual(report['summary']['failed_ids'], ['boom'])
        self.assertEqual(report['cases'][0]['route_reason'], 'metrics')

    def test_runner_full_mode_uses_pipeline_result(self):
        pipeline = MagicMock(return_value=_result('graph', 'Laptop and Mouse'))
        cases = [
            {
                'id': 'g',
                'question': 'quality?',
                'expected_routes': ['graph'],
                'answer_must_include': ['Laptop'],
            }
        ]
        report = run_eval(cases, pipeline_fn=pipeline)
        pipeline.assert_called_once_with('quality?')
        self.assertTrue(report['cases'][0]['passed'])


if __name__ == '__main__':
    unittest.main()
