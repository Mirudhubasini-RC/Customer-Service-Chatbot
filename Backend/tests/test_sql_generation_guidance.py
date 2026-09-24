"""Tests for SQL-generation guidance (median vs highest, quality Notes, lean Schema RAG)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app import SQL_GENERATION_SYSTEM_PROMPT, generate_sql
from schema_rag import SchemaRAG

SCHEMA_DOCS_PATH = (
    Path(__file__).resolve().parent.parent / 'schema_kb' / 'schema_docs.json'
)

QUALITY_ALLOWLIST = (
    'Defective product',
    'Battery life',
    'Durability',
    'Compatibility',
    'Packaging damage',
)
QUALITY_EXCLUDED = (
    'Late delivery',
    'Wrong item received',
    'Pricing concern',
)

HIGHEST_QUALITY_Q = (
    'Which product has the highest sales among products with quality issues?'
)
HIGH_QUALITY_Q = 'Which products have high sales and quality issues?'


def _high_sales_note(docs: dict) -> str:
    for note in docs.get('notes') or []:
        if 'high sales' in note.lower() or 'high-selling' in note.lower():
            return note
    return ''


def _quality_note(docs: dict) -> str:
    for note in docs.get('notes') or []:
        if 'quality issues' in note.lower():
            return note
    return ''


class SqlGenerationGuidanceTests(unittest.TestCase):
    def test_system_prompt_defers_to_notes_for_semantics(self):
        prompt = SQL_GENERATION_SYSTEM_PROMPT.lower()
        self.assertIn('notes are authoritative', prompt)
        self.assertIn('row_number()', prompt)
        self.assertIn('high-selling', prompt)
        self.assertIn('highest', prompt)
        self.assertIn('order by total_quantity desc limit 1', prompt)
        self.assertIn('is_return', prompt)
        self.assertIn('quality-issue', prompt)

    def test_schema_docs_distinguishes_high_vs_highest_sales(self):
        with SCHEMA_DOCS_PATH.open(encoding='utf-8') as f:
            docs = json.load(f)
        note = _high_sales_note(docs).lower()
        self.assertTrue(note)
        self.assertIn('sum(sales.quantity)', note)
        self.assertIn('high-selling', note)
        self.assertIn('median', note)
        self.assertIn('highest', note)
        self.assertIn('order by total_quantity desc', note)
        self.assertIn('limit 1', note)
        self.assertIn('do not use the median rule', note)

    def test_schema_docs_quality_issue_semantics_authoritative_in_notes(self):
        with SCHEMA_DOCS_PATH.open(encoding='utf-8') as f:
            docs = json.load(f)

        note = _quality_note(docs)
        self.assertTrue(note)
        for name in QUALITY_ALLOWLIST:
            self.assertIn(name, note)
        for name in QUALITY_EXCLUDED:
            self.assertIn(name, note)
        self.assertIn('exclude', note.lower())
        self.assertIn('customer_feedback', note.lower())
        self.assertIn('issue_name', note.lower())
        self.assertIn('is_return', note.lower())

    def test_generate_sql_user_context_carries_notes_guidance(self):
        captured = {}

        def fake_llm(messages, max_tokens=320, temperature=0.1):
            captured['messages'] = messages
            return (
                'SELECT p.product_name FROM products p '
                'JOIN sales s ON p.product_id = s.product_id '
                'GROUP BY p.product_name'
            )

        notes = (
            'Notes:\n'
            '- Business semantics — high sales / high-selling vs highest: '
            'SUM(sales.quantity); high → median; highest → ORDER BY total_quantity DESC LIMIT 1\n'
            '- Business semantics — quality issues: issue_name in '
            '(Defective product, Battery life, Durability, Compatibility, Packaging damage); '
            'exclude Late delivery, Wrong item received, Pricing concern'
        )
        fake_rag = MagicMock()
        fake_rag.retrieve.return_value = {
            'retrieved_tables': ['sales', 'issues', 'products'],
            'expanded_tables': ['sales', 'issues', 'products', 'customer_feedback'],
            'scores': {'sales': 0.9},
            'schema_context': notes,
        }

        with patch('app.get_schema_rag', return_value=fake_rag), patch(
            'app.call_llm', side_effect=fake_llm
        ):
            sql, meta = generate_sql(HIGH_QUALITY_Q)

        self.assertIsNotNone(sql)
        system = captured['messages'][0]['content']
        self.assertEqual(system, SQL_GENERATION_SYSTEM_PROMPT)
        user = captured['messages'][1]['content']
        self.assertIn(HIGH_QUALITY_Q, user)
        self.assertIn('median', user.lower())
        self.assertIn('ORDER BY total_quantity DESC LIMIT 1', user)
        for name in QUALITY_ALLOWLIST:
            self.assertIn(name, user)
        self.assertIn('schema_context', meta)

    def test_generate_sql_highest_question_keeps_ranking_guidance_in_context(self):
        captured = {}

        def fake_llm(messages, max_tokens=320, temperature=0.1):
            captured['messages'] = messages
            return (
                'SELECT p.product_name, SUM(s.quantity) AS total_quantity '
                'FROM products p JOIN sales s ON p.product_id = s.product_id '
                'GROUP BY p.product_name ORDER BY total_quantity DESC LIMIT 1'
            )

        fake_rag = MagicMock()
        fake_rag.retrieve.return_value = {
            'retrieved_tables': ['sales', 'issues', 'products'],
            'expanded_tables': ['sales', 'products', 'customer_feedback', 'issues'],
            'scores': {'sales': 0.9},
            'schema_context': (
                'Notes:\n'
                '- high → median; highest/top/most → ORDER BY total_quantity DESC LIMIT 1\n'
                '- quality allowlist: Defective product, Battery life, Durability, '
                'Compatibility, Packaging damage'
            ),
        }

        with patch('app.get_schema_rag', return_value=fake_rag), patch(
            'app.call_llm', side_effect=fake_llm
        ):
            sql, meta = generate_sql(HIGHEST_QUALITY_Q)

        self.assertIsNotNone(sql)
        user = captured['messages'][1]['content']
        self.assertIn('highest', user.lower())
        self.assertIn('ORDER BY total_quantity DESC LIMIT 1', user)
        self.assertIn('Defective product', user)
        low_sql = sql.lower()
        self.assertIn('order by total_quantity desc', low_sql)
        self.assertIn('limit 1', low_sql)


class SchemaRagContextSlimmingTests(unittest.TestCase):
    def test_expansion_skips_brands_categories_unless_seeded(self):
        rag = SchemaRAG.__new__(SchemaRAG)
        rag._fk_outbound = {
            'sales': {'products'},
            'products': {'brands', 'categories'},
            'customer_feedback': {'products', 'issues'},
            'brands': set(),
            'categories': set(),
            'issues': set(),
        }
        rag._fk_inbound = {
            'products': {'sales', 'customer_feedback'},
            'brands': {'products'},
            'categories': {'products'},
            'issues': {'customer_feedback'},
            'sales': set(),
            'customer_feedback': set(),
        }
        rag._lookup_tables = {'brands', 'categories', 'issues'}

        expanded = rag._expand_related(['sales', 'issues', 'products'])
        self.assertIn('customer_feedback', expanded)
        self.assertIn('products', expanded)
        self.assertIn('issues', expanded)
        self.assertNotIn('brands', expanded)
        self.assertNotIn('categories', expanded)

        with_brands = rag._expand_related(['sales', 'brands'])
        self.assertIn('brands', with_brands)
        self.assertIn('products', with_brands)

    def test_format_table_omits_column_meanings(self):
        from schema_rag import _format_table_for_llm

        block = _format_table_for_llm(
            {
                'table_name': 'customer_feedback',
                'purpose': 'Feedback rows',
                'columns': [
                    {
                        'name': 'issue_id',
                        'type': 'INT NULL',
                        'meaning': 'Long prose that must not appear in SQL context',
                    }
                ],
                'foreign_keys': [
                    {
                        'column': 'issue_id',
                        'references_table': 'issues',
                        'references_column': 'issue_id',
                    }
                ],
            }
        )
        self.assertIn('issue_id INT NULL', block)
        self.assertNotIn('Long prose', block)
        self.assertIn('customer_feedback.issue_id → issues.issue_id', block)

    def test_live_context_keeps_semantics_without_brands_categories(self):
        rag = SchemaRAG()
        # Bypass embedding: feed the same seeds the live question retrieves.
        expanded = rag._expand_related(['sales', 'issues', 'products'])
        ctx = rag.build_schema_context(expanded)
        self.assertNotIn('Table: brands', ctx)
        self.assertNotIn('Table: categories', ctx)
        self.assertIn('Table: sales', ctx)
        self.assertIn('Table: customer_feedback', ctx)
        self.assertIn('Table: issues', ctx)
        for name in QUALITY_ALLOWLIST:
            self.assertIn(name, ctx)
        for name in QUALITY_EXCLUDED:
            self.assertIn(name, ctx)
        self.assertIn('SUM(sales.quantity)', ctx)
        self.assertIn('order by total_quantity desc', ctx.lower())
        self.assertIn('limit 1', ctx.lower())
        self.assertIn('median', ctx.lower())
        # Column meanings stripped
        self.assertNotIn('Human-readable product name', ctx)


if __name__ == '__main__':
    unittest.main()
