"""Tests for SQL-generation guidance (median MySQL pattern, returns vs issues)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app import SQL_GENERATION_SYSTEM_PROMPT, generate_sql


class SqlGenerationGuidanceTests(unittest.TestCase):
    def test_system_prompt_requires_window_median_not_limit_offset(self):
        prompt = SQL_GENERATION_SYSTEM_PROMPT.lower()
        self.assertIn('row_number()', prompt)
        self.assertIn('count() over()', prompt)
        self.assertIn('dynamic median', prompt)
        self.assertIn('limit/offset', prompt)
        self.assertIn('is_return', prompt)
        self.assertIn('quality issues', prompt)

    def test_generate_sql_passes_guidance_to_llm(self):
        captured = {}

        def fake_llm(messages, max_tokens=320, temperature=0.1):
            captured['messages'] = messages
            return (
                'SELECT p.product_name FROM products p '
                'JOIN sales s ON p.product_id = s.product_id '
                'GROUP BY p.product_name'
            )

        fake_rag = MagicMock()
        fake_rag.retrieve.return_value = {
            'retrieved_tables': ['sales'],
            'expanded_tables': ['sales', 'products'],
            'scores': {'sales': 0.9},
            'schema_context': (
                'Notes:\n'
                '- Business semantics — high sales ... ROW_NUMBER() ...\n'
                '- Business semantics — quality issues ... issue_id IS NOT NULL'
            ),
        }

        with patch('app.get_schema_rag', return_value=fake_rag), patch(
            'app.call_llm', side_effect=fake_llm
        ):
            sql, meta = generate_sql('Which products have high sales and quality issues?')

        self.assertIsNotNone(sql)
        system = captured['messages'][0]['content']
        self.assertEqual(system, SQL_GENERATION_SYSTEM_PROMPT)
        self.assertIn('ROW_NUMBER()', system)
        self.assertIn('COUNT() OVER()', system)
        user = captured['messages'][1]['content']
        self.assertIn('Which products have high sales and quality issues?', user)
        self.assertIn('schema_context', meta)


if __name__ == '__main__':
    unittest.main()
