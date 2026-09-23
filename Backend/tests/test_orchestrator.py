"""Unit tests for Supervisor + Agent Orchestration (Step 4D). All deps mocked."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from agents.orchestrator import (
    GENERAL_ANSWER,
    run_supervised_question,
    synthesize_sql_and_graph_answer,
)


def _sql_ok(question: str = 'q') -> dict[str, Any]:
    return {
        'agent': 'sql',
        'question': question,
        'schema_context': {'retrieved_tables': ['sales']},
        'sql': 'SELECT SUM(total_price) AS revenue FROM sales',
        'rows': [{'revenue': 1000}],
        'answer': 'Total revenue is 1000.',
        'success': True,
        'error': None,
    }


def _graph_ok(question: str = 'q') -> dict[str, Any]:
    return {
        'agent': 'graph',
        'question': question,
        'retrieval': {
            'intent': {'intent_type': 'products_negative_feedback_returns'},
            'facts': [{'type': 'x', 'product_name': 'Headphones'}],
            'nodes': [{'label': 'Product'}],
            'relationships': [],
            'source': 'neo4j',
        },
        'answer': 'Headphones have negative feedback and a return.',
        'source': 'neo4j',
        'success': True,
        'error': None,
    }


class OrchestratorUnitTests(unittest.TestCase):
    def test_sql_route_calls_only_sql_agent(self):
        route_fn = MagicMock(
            return_value={'route': 'sql', 'reason': 'revenue', 'question': 'q'}
        )
        sql_fn = MagicMock(return_value=_sql_ok('How much revenue did we make?'))
        graph_fn = MagicMock()

        result = run_supervised_question(
            'How much revenue did we make?',
            route_fn=route_fn,
            sql_agent_fn=sql_fn,
            graph_agent_fn=graph_fn,
        )

        sql_fn.assert_called_once_with('How much revenue did we make?')
        graph_fn.assert_not_called()
        self.assertEqual(result['route'], 'sql')
        self.assertIn('sql', result['results'])
        self.assertNotIn('graph', result['results'])
        self.assertTrue(result['success'])
        self.assertEqual(result['answer'], 'Total revenue is 1000.')

    def test_graph_route_calls_only_graph_agent(self):
        route_fn = MagicMock(
            return_value={'route': 'graph', 'reason': 'feedback', 'question': 'q'}
        )
        sql_fn = MagicMock()
        graph_fn = MagicMock(return_value=_graph_ok())

        q = 'Which products have negative feedback and returns?'
        result = run_supervised_question(
            q,
            route_fn=route_fn,
            sql_agent_fn=sql_fn,
            graph_agent_fn=graph_fn,
        )

        graph_fn.assert_called_once_with(q)
        sql_fn.assert_not_called()
        self.assertEqual(result['route'], 'graph')
        self.assertIn('graph', result['results'])
        self.assertNotIn('sql', result['results'])

    def test_general_route_calls_neither(self):
        route_fn = MagicMock(
            return_value={'route': 'general', 'reason': 'concept', 'question': 'q'}
        )
        sql_fn = MagicMock()
        graph_fn = MagicMock()

        result = run_supervised_question(
            'What is customer retention?',
            route_fn=route_fn,
            sql_agent_fn=sql_fn,
            graph_agent_fn=graph_fn,
        )

        sql_fn.assert_not_called()
        graph_fn.assert_not_called()
        self.assertEqual(result['route'], 'general')
        self.assertEqual(result['answer'], GENERAL_ANSWER)
        self.assertTrue(result['success'])
        self.assertEqual(
            result['results']['general']['reason'],
            'general_agent_not_implemented',
        )

    def test_sql_and_graph_calls_both_and_synthesizes(self):
        q = 'Which high-selling products also have negative feedback?'
        route_fn = MagicMock(
            return_value={'route': 'sql_and_graph', 'reason': 'both', 'question': q}
        )
        sql_result = _sql_ok(q)
        graph_result = _graph_ok(q)
        sql_fn = MagicMock(return_value=sql_result)
        graph_fn = MagicMock(return_value=graph_result)
        synth = MagicMock(return_value='Combined: high sellers with negative feedback.')

        result = run_supervised_question(
            q,
            route_fn=route_fn,
            sql_agent_fn=sql_fn,
            graph_agent_fn=graph_fn,
            synthesize_fn=synth,
        )

        sql_fn.assert_called_once_with(q)
        graph_fn.assert_called_once_with(q)
        self.assertEqual(synth.call_count, 1)
        args, kwargs = synth.call_args
        self.assertEqual(args[0], q)
        self.assertEqual(args[1], sql_result)
        self.assertEqual(args[2], graph_result)
        self.assertEqual(result['route'], 'sql_and_graph')
        self.assertEqual(result['results']['sql'], sql_result)
        self.assertEqual(result['results']['graph'], graph_result)
        self.assertEqual(
            result['answer'],
            'Combined: high sellers with negative feedback.',
        )
        self.assertTrue(result['success'])

    def test_synthesis_receives_both_results_via_llm_messages(self):
        """synthesize_sql_and_graph_answer packs both agents into the LLM prompt."""
        captured: dict[str, Any] = {}

        def fake_llm(messages, max_tokens=320, temperature=0.2):
            captured['messages'] = messages
            return 'Synthesized answer.'

        sql_result = _sql_ok()
        graph_result = _graph_ok()
        answer = synthesize_sql_and_graph_answer(
            'Which high-selling products also have negative feedback?',
            sql_result,
            graph_result,
            llm_call=fake_llm,
        )

        self.assertEqual(answer, 'Synthesized answer.')
        user = captured['messages'][1]['content']
        self.assertIn('sql_agent', user)
        self.assertIn('graph_agent', user)
        self.assertIn('Headphones', user)
        self.assertIn('revenue', user.lower())
        system = captured['messages'][0]['content']
        self.assertIn('Do NOT invent', system)
        self.assertIn('Do NOT generate SQL', system)

    def test_agent_failure_partial_sql_and_graph(self):
        q = 'Which high-selling products also have negative feedback?'
        route_fn = MagicMock(
            return_value={'route': 'sql_and_graph', 'reason': 'both', 'question': q}
        )
        sql_fail = {
            'agent': 'sql',
            'question': q,
            'success': False,
            'error': 'sql_execution_failed',
            'answer': 'SQL failed',
            'rows': [],
            'sql': None,
        }
        graph_result = _graph_ok(q)
        synth = MagicMock(return_value='Using graph only: Headphones.')

        result = run_supervised_question(
            q,
            route_fn=route_fn,
            sql_agent_fn=lambda _q: sql_fail,
            graph_agent_fn=lambda _q: graph_result,
            synthesize_fn=synth,
        )

        self.assertEqual(result['results']['sql'], sql_fail)
        self.assertEqual(result['results']['graph'], graph_result)
        self.assertFalse(result['success'])
        self.assertIn('partial_sql_and_graph', result['error'])
        self.assertIn('sql:', result['error'])
        self.assertEqual(result['answer'], 'Using graph only: Headphones.')
        synth.assert_called_once()

    def test_agent_exception_handled(self):
        route_fn = MagicMock(
            return_value={'route': 'sql', 'reason': 'x', 'question': 'q'}
        )

        def boom(_q: str):
            raise RuntimeError('crash')

        result = run_supervised_question(
            'How much revenue did we make?',
            route_fn=route_fn,
            sql_agent_fn=boom,
            graph_agent_fn=MagicMock(),
        )

        self.assertFalse(result['success'])
        self.assertIn('agent_exception', result['error'])
        self.assertEqual(result['route'], 'sql')
        self.assertIn('sql', result['results'])

    def test_preserves_route_and_agent_results(self):
        q = 'How much revenue did we make?'
        sql_result = _sql_ok(q)
        result = run_supervised_question(
            q,
            route_fn=lambda _q: {'route': 'sql', 'reason': 'rev', 'question': q},
            sql_agent_fn=lambda _q: sql_result,
            graph_agent_fn=MagicMock(),
        )
        self.assertEqual(result['question'], q)
        self.assertEqual(result['route'], 'sql')
        self.assertEqual(result['routing']['reason'], 'rev')
        self.assertEqual(result['results']['sql'], sql_result)

    def test_malformed_supervisor_routing_handled(self):
        sql_fn = MagicMock()
        graph_fn = MagicMock()

        result = run_supervised_question(
            'What is customer retention?',
            route_fn=lambda _q: 'not-a-dict',
            sql_agent_fn=sql_fn,
            graph_agent_fn=graph_fn,
        )

        sql_fn.assert_not_called()
        graph_fn.assert_not_called()
        self.assertEqual(result['route'], 'general')
        self.assertTrue(result['success'])

    def test_supervisor_exception_handled(self):
        def boom(_q: str):
            raise RuntimeError('router down')

        result = run_supervised_question(
            'What is customer retention?',
            route_fn=boom,
            sql_agent_fn=MagicMock(),
            graph_agent_fn=MagicMock(),
        )
        self.assertEqual(result['route'], 'general')
        self.assertIn('failed', result['routing']['reason'].lower())

    def test_invalid_route_defaults_to_general(self):
        result = run_supervised_question(
            'Hello',
            route_fn=lambda _q: {'route': 'vector', 'reason': 'x', 'question': 'Hello'},
            sql_agent_fn=MagicMock(),
            graph_agent_fn=MagicMock(),
        )
        self.assertEqual(result['route'], 'general')


if __name__ == '__main__':
    unittest.main()
