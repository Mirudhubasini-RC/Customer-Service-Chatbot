"""Unit tests for Business Graph Retrieval intent + retriever (Step 3C)."""

from __future__ import annotations

import unittest
from typing import Any

from business_graph.intent import (
    BRANDS_WITH_NEGATIVE_FEEDBACK,
    PRODUCTS_HIGH_SALES_AND_QUALITY_ISSUES,
    PRODUCTS_NEGATIVE_FEEDBACK_RETURNS,
    PRODUCTS_WITH_QUALITY_ISSUES,
    QUALITY_ISSUE_NAMES,
    parse_retrieval_intent,
)
from business_graph.retriever import GraphRetriever


class FakeNeo4jStore:
    """Minimal Cypher runner for unit tests (no live Neo4j)."""

    def __init__(self, responses: dict[str, list[dict[str, Any]]] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def run_cypher(
        self, cypher: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        self.calls.append((cypher, parameters))
        key = self._key(cypher)
        return list(self.responses.get(key, []))

    @staticmethod
    def _key(cypher: str) -> str:
        text = ' '.join(cypher.split())
        if 'ABOUT_ISSUE' in text and 'Brand' in text and 'negative' in text:
            return 'brands_negative'
        if 'is_return' in text or '$sentiment' in text:
            return 'negative_returns'
        if 'median' in text or 'sum(s.quantity)' in text and 'issue_names' in text:
            return 'high_sales_agg'
        if 'sum(s.quantity) AS sales_units' in text and 'ABOUT_ISSUE' not in text:
            return 'sales_units'
        if 'product_ids' in text:
            return 'high_sales_detail'
        if 'ABOUT_ISSUE' in text and 'Brand' in text:
            return 'quality_summary'
        if 'ABOUT_ISSUE' in text and 'RETURN p, f, i' in text:
            return 'quality_paths'
        if 'HAS_SALE' in text and 'product_id' in text:
            return 'product_sales'
        return 'default'


class IntentParsingTests(unittest.TestCase):
    def test_quality_issues(self):
        intent = parse_retrieval_intent('Which products have quality issues?')
        self.assertEqual(intent.intent_type, PRODUCTS_WITH_QUALITY_ISSUES)
        self.assertIn('Issue', intent.entities)
        self.assertEqual(
            intent.filters.get('quality_issue_names'), list(QUALITY_ISSUE_NAMES)
        )

    def test_quality_issue_names_exclude_non_quality(self):
        excluded = {'Late delivery', 'Wrong item received', 'Pricing concern'}
        self.assertTrue(excluded.isdisjoint(QUALITY_ISSUE_NAMES))
        self.assertEqual(
            set(QUALITY_ISSUE_NAMES),
            {
                'Defective product',
                'Battery life',
                'Durability',
                'Compatibility',
                'Packaging damage',
            },
        )

    def test_negative_feedback_returns(self):
        intent = parse_retrieval_intent(
            'Which products have negative feedback and returns?'
        )
        self.assertEqual(intent.intent_type, PRODUCTS_NEGATIVE_FEEDBACK_RETURNS)
        self.assertEqual(intent.filters.get('sentiment'), 'negative')
        self.assertTrue(intent.filters.get('is_return'))

    def test_brands_negative_feedback(self):
        intent = parse_retrieval_intent(
            'Which brands have products with negative feedback?'
        )
        self.assertEqual(intent.intent_type, BRANDS_WITH_NEGATIVE_FEEDBACK)

    def test_high_sales_and_quality(self):
        intent = parse_retrieval_intent(
            'Which products have high sales and quality issues?'
        )
        self.assertEqual(intent.intent_type, PRODUCTS_HIGH_SALES_AND_QUALITY_ISSUES)
        self.assertEqual(
            intent.filters.get('quality_issue_names'), list(QUALITY_ISSUE_NAMES)
        )
        self.assertEqual(intent.filters.get('sales_threshold'), 'median_or_above')

    def test_highest_sales_and_quality_intent(self):
        intent = parse_retrieval_intent(
            'Which product has the highest sales among products with quality issues?'
        )
        self.assertEqual(intent.intent_type, PRODUCTS_HIGH_SALES_AND_QUALITY_ISSUES)
        self.assertEqual(intent.filters.get('sales_threshold'), 'highest')
        self.assertEqual(
            intent.filters.get('quality_issue_names'), list(QUALITY_ISSUE_NAMES)
        )


class GraphRetrieverUnitTests(unittest.TestCase):
    def test_quality_issues_builds_context(self):
        store = FakeNeo4jStore(
            {
                'quality_summary': [
                    {
                        'p': {
                            'key': 'Product:3',
                            'product_id': 3,
                            'product_name': 'Headphones',
                        },
                        'b': {'key': 'Brand:2', 'brand_id': 2, 'brand_name': 'SoundMax'},
                        'issue_names': ['Durability'],
                        'feedback_count': 1,
                    }
                ],
                'quality_paths': [
                    {
                        'p': {
                            'key': 'Product:3',
                            'product_id': 3,
                            'product_name': 'Headphones',
                        },
                        'f': {
                            'key': 'CustomerFeedback:4',
                            'feedback_id': 4,
                            'sentiment': 'negative',
                            'is_return': True,
                        },
                        'i': {
                            'key': 'Issue:6',
                            'issue_id': 6,
                            'issue_name': 'Durability',
                        },
                    }
                ],
            }
        )
        retriever = GraphRetriever(store)
        ctx = retriever.retrieve('Which products have quality issues?')
        self.assertEqual(ctx['source'], 'neo4j')
        self.assertTrue(any(n.get('product_name') == 'Headphones' for n in ctx['nodes']))
        self.assertTrue(
            any(f.get('type') == 'product_quality_issues' for f in ctx['facts'])
        )
        rel_types = {r['type'] for r in ctx['relationships']}
        self.assertIn('HAS_FEEDBACK', rel_types)
        self.assertIn('ABOUT_ISSUE', rel_types)
        # Cypher must filter to the quality-issue allowlist
        self.assertTrue(
            any(
                (params or {}).get('quality_issue_names') == list(QUALITY_ISSUE_NAMES)
                for _, params in store.calls
            )
        )
        self.assertTrue(
            any(
                'i.issue_name IN $quality_issue_names' in ' '.join(cypher.split())
                for cypher, _ in store.calls
            )
        )

    def test_high_sales_and_quality_filters_issue_names(self):
        store = FakeNeo4jStore(
            {
                'sales_units': [
                    {'product_id': 6, 'sales_units': 70},
                    {'product_id': 1, 'sales_units': 10},
                ],
                'high_sales_agg': [
                    {
                        'p': {
                            'key': 'Product:6',
                            'product_id': 6,
                            'product_name': 'Mouse',
                        },
                        'b': {
                            'key': 'Brand:4',
                            'brand_id': 4,
                            'brand_name': 'OfficePro',
                        },
                        'issue_names': ['Defective product'],
                        'sales_units': 70,
                        'sales_revenue': 2000.0,
                    }
                ],
                'high_sales_detail': [],
            }
        )
        retriever = GraphRetriever(store)
        ctx = retriever.retrieve(
            'Which products have high sales and quality issues?'
        )
        self.assertTrue(
            any(
                f.get('type') == 'product_high_sales_with_quality_issues'
                for f in ctx['facts']
            )
        )
        self.assertTrue(
            any(
                f.get('type') == 'sales_threshold' and f.get('rule') == 'median_or_above'
                for f in ctx['facts']
            )
        )
        quality_calls = [
            (cypher, params)
            for cypher, params in store.calls
            if params and 'quality_issue_names' in params
        ]
        self.assertGreaterEqual(len(quality_calls), 1)
        for cypher, params in quality_calls:
            self.assertEqual(params['quality_issue_names'], list(QUALITY_ISSUE_NAMES))
            self.assertIn('i.issue_name IN $quality_issue_names', ' '.join(cypher.split()))

    def test_highest_sales_and_quality_returns_only_top_product(self):
        store = FakeNeo4jStore(
            {
                'high_sales_agg': [
                    {
                        'p': {
                            'key': 'Product:6',
                            'product_id': 6,
                            'product_name': 'Mouse',
                        },
                        'b': {
                            'key': 'Brand:4',
                            'brand_id': 4,
                            'brand_name': 'PowerLink',
                        },
                        'issue_names': ['Compatibility'],
                        'sales_units': 70,
                        'sales_revenue': 2099.3,
                    },
                    {
                        'p': {
                            'key': 'Product:3',
                            'product_id': 3,
                            'product_name': 'Headphones',
                        },
                        'b': {
                            'key': 'Brand:2',
                            'brand_id': 2,
                            'brand_name': 'SoundMax',
                        },
                        'issue_names': ['Durability'],
                        'sales_units': 25,
                        'sales_revenue': 3749.75,
                    },
                ],
                'high_sales_detail': [
                    {
                        'p': {
                            'key': 'Product:6',
                            'product_id': 6,
                            'product_name': 'Mouse',
                        },
                        'f': {
                            'key': 'CustomerFeedback:6',
                            'feedback_id': 6,
                            'sentiment': 'negative',
                        },
                        'i': {
                            'key': 'Issue:7',
                            'issue_id': 7,
                            'issue_name': 'Compatibility',
                        },
                        's': {
                            'key': 'Sale:6',
                            'sale_id': 6,
                            'quantity': 30,
                        },
                    }
                ],
            }
        )
        retriever = GraphRetriever(store)
        ctx = retriever.retrieve(
            'Which product has the highest sales among products with quality issues?'
        )
        product_facts = [
            f
            for f in ctx['facts']
            if f.get('type') == 'product_high_sales_with_quality_issues'
        ]
        self.assertEqual(len(product_facts), 1)
        self.assertEqual(product_facts[0]['product_name'], 'Mouse')
        self.assertEqual(product_facts[0]['sales_units'], 70)
        self.assertTrue(
            any(
                f.get('type') == 'sales_threshold' and f.get('rule') == 'highest'
                for f in ctx['facts']
            )
        )
        detail_calls = [
            params
            for cypher, params in store.calls
            if params and 'product_ids' in params
        ]
        self.assertEqual(len(detail_calls), 1)
        self.assertEqual(detail_calls[0]['product_ids'], [6])
        # Highest path should not need the all-products sales_units median query.
        self.assertFalse(
            any(key == 'sales_units' for key, _ in (
                (FakeNeo4jStore._key(c), p) for c, p in store.calls
            ))
        )

    def test_negative_returns_filters(self):
        store = FakeNeo4jStore(
            {
                'negative_returns': [
                    {
                        'p': {
                            'key': 'Product:1',
                            'product_id': 1,
                            'product_name': 'Laptop',
                        },
                        'b': {
                            'key': 'Brand:1',
                            'brand_id': 1,
                            'brand_name': 'TechNova',
                        },
                        'f': {
                            'key': 'CustomerFeedback:1',
                            'feedback_id': 1,
                            'sentiment': 'negative',
                            'is_return': True,
                            'return_reason': 'Defective display',
                        },
                        'i': {
                            'key': 'Issue:1',
                            'issue_id': 1,
                            'issue_name': 'Defective product',
                        },
                    }
                ]
            }
        )
        retriever = GraphRetriever(store)
        ctx = retriever.retrieve(
            'Which products have negative feedback and returns?'
        )
        self.assertTrue(any(f.get('is_return') for f in ctx['facts'] if 'is_return' in f))
        # Ensure Cypher was parameterized with sentiment
        self.assertTrue(
            any(
                (params or {}).get('sentiment') == 'negative'
                for _, params in store.calls
            )
        )

    def test_structured_product_sales(self):
        store = FakeNeo4jStore(
            {
                'product_sales': [
                    {
                        'p': {
                            'key': 'Product:6',
                            'product_id': 6,
                            'product_name': 'Mouse',
                        },
                        's': {
                            'key': 'Sale:6',
                            'sale_id': 6,
                            'quantity': 30,
                            'total_price': 899.7,
                        },
                    }
                ]
            }
        )
        retriever = GraphRetriever(store)
        ctx = retriever.retrieve_product_sales(6)
        self.assertEqual(ctx['facts'][0]['sales_units'], 30)
        self.assertTrue(
            any(r['type'] == 'HAS_SALE' for r in ctx['relationships'])
        )


if __name__ == '__main__':
    unittest.main()
