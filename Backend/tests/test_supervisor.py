"""Unit tests for Supervisor Agent routing (Step 4A). LLM is mocked."""

from __future__ import annotations

import unittest

from agents.supervisor import VALID_ROUTES, route_question


class SupervisorRoutingTests(unittest.TestCase):
    def test_valid_route_parsing_sql(self):
        def fake_llm(messages, max_tokens=120, temperature=0.0):
            return (
                '{"route":"sql","reason":"Needs revenue aggregate from sales.",'
                '"question":"How much revenue did we make?"}'
            )

        result = route_question('How much revenue did we make?', llm_call=fake_llm)
        self.assertEqual(result['route'], 'sql')
        self.assertIn('revenue', result['reason'].lower())
        self.assertEqual(result['question'], 'How much revenue did we make?')

    def test_valid_route_parsing_graph(self):
        def fake_llm(messages, max_tokens=120, temperature=0.0):
            return (
                '{"route":"graph","reason":"Needs feedback-return relationships.",'
                '"question":"Which products have negative feedback and returns?"}'
            )

        q = 'Which products have negative feedback and returns?'
        result = route_question(q, llm_call=fake_llm)
        self.assertEqual(result['route'], 'graph')
        self.assertEqual(result['question'], q)

    def test_sql_and_graph_supported(self):
        def fake_llm(messages, max_tokens=120, temperature=0.0):
            return (
                '{"route":"sql_and_graph","reason":"Needs sales ranking and feedback links.",'
                '"question":"Which high-selling products also have negative feedback?"}'
            )

        q = 'Which high-selling products also have negative feedback?'
        result = route_question(q, llm_call=fake_llm)
        self.assertEqual(result['route'], 'sql_and_graph')
        self.assertIn(result['route'], VALID_ROUTES)
        self.assertEqual(result['question'], q)

    def test_invalid_route_fallback(self):
        def fake_llm(messages, max_tokens=120, temperature=0.0):
            return '{"route":"vector","reason":"oops","question":"x"}'

        result = route_question('What is customer retention?', llm_call=fake_llm)
        self.assertEqual(result['route'], 'general')
        self.assertIn('Invalid route', result['reason'])
        self.assertEqual(result['question'], 'What is customer retention?')

    def test_malformed_llm_response_fallback(self):
        def fake_llm(messages, max_tokens=120, temperature=0.0):
            return 'I think this should go to SQL maybe?'

        result = route_question('How much revenue did we make?', llm_call=fake_llm)
        self.assertEqual(result['route'], 'general')
        self.assertIn('Invalid or missing JSON', result['reason'])
        self.assertEqual(result['question'], 'How much revenue did we make?')

    def test_fenced_json_still_parses(self):
        def fake_llm(messages, max_tokens=120, temperature=0.0):
            return (
                '```json\n'
                '{"route":"general","reason":"Conceptual definition.",'
                '"question":"What is customer retention?"}\n'
                '```'
            )

        q = 'What is customer retention?'
        result = route_question(q, llm_call=fake_llm)
        self.assertEqual(result['route'], 'general')
        self.assertEqual(result['question'], q)

    def test_preserves_original_question_over_model_rewrite(self):
        def fake_llm(messages, max_tokens=120, temperature=0.0):
            return (
                '{"route":"sql","reason":"ok",'
                '"question":"totally different rewritten question"}'
            )

        original = 'How much revenue did we make?'
        result = route_question(original, llm_call=fake_llm)
        self.assertEqual(result['question'], original)

    def test_llm_exception_fallback(self):
        def fake_llm(messages, max_tokens=120, temperature=0.0):
            raise RuntimeError('network down')

        result = route_question('Hello?', llm_call=fake_llm)
        self.assertEqual(result['route'], 'general')
        self.assertIn('failed', result['reason'].lower())
        self.assertEqual(result['question'], 'Hello?')

    def test_empty_question_fallback(self):
        result = route_question('   ', llm_call=lambda *a, **k: '{"route":"sql"}')
        self.assertEqual(result['route'], 'general')
        self.assertEqual(result['question'], '')


if __name__ == '__main__':
    unittest.main()
