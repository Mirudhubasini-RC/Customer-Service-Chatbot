"""Unit tests for SQL Agent (Step 4B). LLM and DB calls are mocked."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from agents.sql_agent import EMPTY_ROWS_ANSWER, run_sql_agent


def _schema_meta(**overrides: Any) -> dict[str, Any]:
    base = {
        'retrieved_tables': ['sales'],
        'expanded_tables': ['sales', 'products'],
        'scores': {'sales': 0.91},
        'schema_context': 'Table: sales\nColumns:\n  - amount ...',
    }
    base.update(overrides)
    return base


class SqlAgentUnitTests(unittest.TestCase):
    def test_schema_retrieval_is_used(self):
        """generate_sql (Schema RAG path) is invoked and schema meta is returned."""
        generate = MagicMock(
            return_value=(
                'SELECT SUM(amount) AS revenue FROM sales',
                _schema_meta(),
            )
        )
        execute = MagicMock(return_value=[{'revenue': 1000.0}])
        explain = MagicMock(return_value='Total revenue is 1000.')
        safe = MagicMock(return_value=True)

        result = run_sql_agent(
            'How much revenue did we make?',
            generate_sql_fn=generate,
            is_safe_select_fn=safe,
            execute_sql_fn=execute,
            explain_rows_fn=explain,
        )

        generate.assert_called_once_with('How much revenue did we make?')
        self.assertEqual(result['schema_context']['retrieved_tables'], ['sales'])
        self.assertIn('schema_context', result['schema_context'])
        self.assertTrue(result['success'])

    def test_generated_sql_passed_through_safety_validation(self):
        sql = 'SELECT SUM(amount) AS revenue FROM sales'
        generate = MagicMock(return_value=(sql, _schema_meta()))
        safe = MagicMock(return_value=True)
        execute = MagicMock(return_value=[{'revenue': 42}])
        explain = MagicMock(return_value='Revenue is 42.')

        run_sql_agent(
            'How much revenue did we make?',
            generate_sql_fn=generate,
            is_safe_select_fn=safe,
            execute_sql_fn=execute,
            explain_rows_fn=explain,
        )

        safe.assert_called_once_with(sql)

    def test_unsafe_sql_never_executed(self):
        unsafe = 'DELETE FROM sales'
        generate = MagicMock(return_value=(unsafe, _schema_meta()))
        safe = MagicMock(return_value=False)
        execute = MagicMock()
        explain = MagicMock()

        result = run_sql_agent(
            'Delete everything',
            generate_sql_fn=generate,
            is_safe_select_fn=safe,
            execute_sql_fn=execute,
            explain_rows_fn=explain,
        )

        execute.assert_not_called()
        explain.assert_not_called()
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'unsafe_sql_rejected')
        self.assertEqual(result['sql'], unsafe)
        self.assertEqual(result['rows'], [])
        self.assertIn('rejected', result['answer'].lower())

    def test_successful_execution_returns_structured_results(self):
        sql = 'SELECT product_name, SUM(quantity) AS qty FROM sales GROUP BY product_name'
        rows = [{'product_name': 'Laptop', 'qty': 10}]
        generate = MagicMock(return_value=(sql, _schema_meta()))
        result = run_sql_agent(
            'Which products sold the most?',
            generate_sql_fn=generate,
            is_safe_select_fn=lambda s: True,
            execute_sql_fn=lambda s: rows,
            explain_rows_fn=lambda q, s, r: 'Laptop sold the most.',
        )

        self.assertEqual(result['agent'], 'sql')
        self.assertEqual(result['question'], 'Which products sold the most?')
        self.assertEqual(result['sql'], sql)
        self.assertEqual(result['rows'], rows)
        self.assertEqual(result['answer'], 'Laptop sold the most.')
        self.assertTrue(result['success'])
        self.assertIsNone(result['error'])

    def test_empty_results_handled(self):
        generate = MagicMock(
            return_value=('SELECT * FROM sales WHERE 1=0', _schema_meta())
        )
        explain = MagicMock()

        result = run_sql_agent(
            'What was the revenue for August 2099?',
            generate_sql_fn=generate,
            is_safe_select_fn=lambda s: True,
            execute_sql_fn=lambda s: [],
            explain_rows_fn=explain,
        )

        explain.assert_not_called()
        self.assertTrue(result['success'])
        self.assertEqual(result['rows'], [])
        self.assertEqual(result['answer'], EMPTY_ROWS_ANSWER)

    def test_sql_generation_failure_handled(self):
        def boom(_question: str):
            raise RuntimeError('LLM down')

        execute = MagicMock()
        result = run_sql_agent(
            'How much revenue did we make?',
            generate_sql_fn=boom,
            is_safe_select_fn=lambda s: True,
            execute_sql_fn=execute,
            explain_rows_fn=lambda *a: 'nope',
        )

        execute.assert_not_called()
        self.assertFalse(result['success'])
        self.assertIn('sql_generation_failed', result['error'])
        self.assertEqual(result['agent'], 'sql')
        self.assertEqual(result['question'], 'How much revenue did we make?')

    def test_sql_generation_returns_none(self):
        generate = MagicMock(return_value=(None, _schema_meta()))
        execute = MagicMock()

        result = run_sql_agent(
            'Unsupported analytics question',
            generate_sql_fn=generate,
            is_safe_select_fn=lambda s: True,
            execute_sql_fn=execute,
            explain_rows_fn=lambda *a: 'nope',
        )

        execute.assert_not_called()
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'sql_generation_unsupported_or_invalid')
        self.assertIsNone(result['sql'])

    def test_execution_failure_handled(self):
        generate = MagicMock(
            return_value=('SELECT 1', _schema_meta())
        )

        def fail_exec(_sql: str):
            raise RuntimeError('MySQL down')

        result = run_sql_agent(
            'How much revenue did we make?',
            generate_sql_fn=generate,
            is_safe_select_fn=lambda s: True,
            execute_sql_fn=fail_exec,
            explain_rows_fn=lambda *a: 'nope',
        )

        self.assertFalse(result['success'])
        self.assertIn('sql_execution_failed', result['error'])
        self.assertEqual(result['sql'], 'SELECT 1')

    def test_empty_question(self):
        result = run_sql_agent(
            '   ',
            generate_sql_fn=lambda q: ('SELECT 1', _schema_meta()),
            is_safe_select_fn=lambda s: True,
            execute_sql_fn=lambda s: [{'x': 1}],
            explain_rows_fn=lambda *a: 'x',
        )
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'empty_question')


if __name__ == '__main__':
    unittest.main()
