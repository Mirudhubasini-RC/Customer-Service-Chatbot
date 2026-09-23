"""Tests for Graph RAG answer generation (Step 3D)."""

from __future__ import annotations

import unittest
from typing import Any

from business_graph.graph_answer import (
    build_graph_answer_messages,
    format_graph_context_for_prompt,
    generate_graph_answer,
    is_insufficient_retrieval,
    run_graph_rag,
)


class GraphAnswerUnitTests(unittest.TestCase):
    def test_insufficient_empty_context(self):
        retrieval = {
            'question': 'Anything?',
            'nodes': [],
            'relationships': [],
            'facts': [],
            'source': 'neo4j',
        }
        self.assertTrue(is_insufficient_retrieval(retrieval))
        answer = generate_graph_answer('Anything?', retrieval, llm_call=lambda *a, **k: 'SHOULD_NOT_RUN')
        self.assertIn('insufficient', answer.lower())

    def test_insufficient_unsupported_fact(self):
        retrieval = {
            'facts': [{'type': 'unsupported', 'message': 'no pattern'}],
            'nodes': [],
            'relationships': [],
        }
        self.assertTrue(is_insufficient_retrieval(retrieval))

    def test_context_passed_to_llm(self):
        captured: dict[str, Any] = {}

        def fake_llm(messages, max_tokens=280, temperature=0.2):
            captured['messages'] = messages
            captured['max_tokens'] = max_tokens
            return 'Headphones have a Durability issue with a return.'

        retrieval = {
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
        answer = generate_graph_answer(
            'Which products have quality issues?',
            retrieval,
            llm_call=fake_llm,
        )
        self.assertEqual(answer, 'Headphones have a Durability issue with a return.')
        self.assertEqual(len(captured['messages']), 2)
        user = captured['messages'][1]['content']
        self.assertIn('Headphones', user)
        self.assertIn('Durability', user)
        self.assertIn('Neo4j graph context', user)
        system = captured['messages'][0]['content']
        self.assertIn('ONLY using the supplied Neo4j', system)
        self.assertIn('Do not generate SQL', system)

    def test_run_graph_rag_preserves_retrieval(self):
        retrieval = {
            'question': 'q',
            'nodes': [{'key': 'Product:1', 'label': 'Product', 'product_name': 'Laptop'}],
            'relationships': [],
            'facts': [{'type': 'product_quality_issues', 'product_name': 'Laptop'}],
            'source': 'neo4j',
        }
        result = run_graph_rag(
            'Which products have quality issues?',
            retrieval=retrieval,
            llm_call=lambda *a, **k: 'Laptop has quality issues in the graph.',
        )
        self.assertEqual(result['source'], 'neo4j')
        self.assertEqual(result['retrieval'], retrieval)
        self.assertIn('Laptop', result['answer'])
        self.assertEqual(result['question'], 'Which products have quality issues?')

    def test_prompt_builder_includes_guardrails(self):
        retrieval = {
            'facts': [{'type': 'x'}],
            'nodes': [],
            'relationships': [],
            'intent': {},
        }
        messages = build_graph_answer_messages('Q?', retrieval)
        blob = format_graph_context_for_prompt(retrieval)
        self.assertIn('"facts"', blob)
        self.assertIn('insufficient', messages[0]['content'].lower())


if __name__ == '__main__':
    unittest.main()
