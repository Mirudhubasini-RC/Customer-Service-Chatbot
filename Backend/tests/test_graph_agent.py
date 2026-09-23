"""Unit tests for Graph Agent (Step 4C). Retrieval and answer gen are mocked."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from agents.graph_agent import run_graph_agent


def _retrieval(**overrides: Any) -> dict[str, Any]:
    base = {
        'question': 'Which products have quality issues?',
        'intent': {'intent_type': 'products_with_quality_issues'},
        'nodes': [
            {
                'key': 'Product:3',
                'label': 'Product',
                'product_id': 3,
                'product_name': 'Headphones',
            }
        ],
        'relationships': [
            {'start': 'Product:3', 'type': 'HAS_FEEDBACK', 'end': 'CustomerFeedback:4'}
        ],
        'facts': [
            {
                'type': 'product_quality_issues',
                'product_name': 'Headphones',
                'issues': ['Durability'],
            }
        ],
        'source': 'neo4j',
    }
    base.update(overrides)
    return base


class GraphAgentUnitTests(unittest.TestCase):
    def test_retrieval_is_called(self):
        retrieve = MagicMock(return_value=_retrieval())
        answer_fn = MagicMock(return_value='Headphones have Durability issues.')

        run_graph_agent(
            'Which products have quality issues?',
            retrieve_fn=retrieve,
            generate_answer_fn=answer_fn,
        )

        retrieve.assert_called_once_with('Which products have quality issues?')

    def test_retrieved_context_passed_to_answer_generation(self):
        retrieval = _retrieval()
        retrieve = MagicMock(return_value=retrieval)
        answer_fn = MagicMock(return_value='Grounded answer.')

        run_graph_agent(
            'Which products have quality issues?',
            retrieve_fn=retrieve,
            generate_answer_fn=answer_fn,
        )

        answer_fn.assert_called_once_with(
            'Which products have quality issues?',
            retrieval,
        )

    def test_result_preserves_retrieval_data(self):
        retrieval = _retrieval()
        result = run_graph_agent(
            'Which products have quality issues?',
            retrieve_fn=lambda q: retrieval,
            generate_answer_fn=lambda q, r: 'ok',
        )

        self.assertEqual(result['retrieval'], retrieval)
        self.assertEqual(
            result['retrieval']['facts'][0]['product_name'],
            'Headphones',
        )

    def test_successful_result_structure(self):
        result = run_graph_agent(
            'Which products have quality issues?',
            retrieve_fn=lambda q: _retrieval(),
            generate_answer_fn=lambda q, r: 'Headphones have Durability issues.',
        )

        self.assertEqual(result['agent'], 'graph')
        self.assertEqual(result['question'], 'Which products have quality issues?')
        self.assertEqual(result['source'], 'neo4j')
        self.assertTrue(result['success'])
        self.assertIsNone(result['error'])
        self.assertEqual(result['answer'], 'Headphones have Durability issues.')
        self.assertIn('facts', result['retrieval'])

    def test_empty_unsupported_retrieval_handled(self):
        unsupported = {
            'question': 'What is the weather?',
            'intent': {'intent_type': 'unsupported'},
            'nodes': [],
            'relationships': [],
            'facts': [{'type': 'unsupported', 'message': 'no pattern'}],
            'source': 'neo4j',
        }
        answer_fn = MagicMock(
            return_value=(
                'The available Neo4j graph data is insufficient to answer '
                'this question.'
            )
        )

        result = run_graph_agent(
            'What is the weather?',
            retrieve_fn=lambda q: unsupported,
            generate_answer_fn=answer_fn,
        )

        answer_fn.assert_called_once()
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'unsupported_or_empty_graph')
        self.assertEqual(result['retrieval'], unsupported)
        self.assertIn('insufficient', result['answer'].lower())

    def test_empty_context_handled(self):
        empty = {
            'intent': {'intent_type': 'products_with_quality_issues'},
            'nodes': [],
            'relationships': [],
            'facts': [],
            'source': 'neo4j',
        }
        result = run_graph_agent(
            'Which products have quality issues?',
            retrieve_fn=lambda q: empty,
            generate_answer_fn=lambda q, r: 'No matching business-graph facts.',
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'unsupported_or_empty_graph')
        self.assertEqual(result['retrieval'], empty)

    def test_neo4j_retrieval_failure_handled(self):
        def boom(_question: str):
            raise RuntimeError('Aura down')

        answer_fn = MagicMock()
        result = run_graph_agent(
            'Which products have quality issues?',
            retrieve_fn=boom,
            generate_answer_fn=answer_fn,
        )

        answer_fn.assert_not_called()
        self.assertFalse(result['success'])
        self.assertIn('retrieval_failed', result['error'])
        self.assertEqual(result['agent'], 'graph')
        self.assertEqual(result['retrieval'], {})

    def test_qwen_answer_failure_handled(self):
        retrieval = _retrieval()

        def boom(_q: str, _r: dict):
            raise RuntimeError('Qwen down')

        result = run_graph_agent(
            'Which products have quality issues?',
            retrieve_fn=lambda q: retrieval,
            generate_answer_fn=boom,
        )

        self.assertFalse(result['success'])
        self.assertIn('answer_generation_failed', result['error'])
        self.assertEqual(result['retrieval'], retrieval)

    def test_empty_question(self):
        result = run_graph_agent(
            '  ',
            retrieve_fn=lambda q: _retrieval(),
            generate_answer_fn=lambda q, r: 'nope',
        )
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'empty_question')


if __name__ == '__main__':
    unittest.main()
