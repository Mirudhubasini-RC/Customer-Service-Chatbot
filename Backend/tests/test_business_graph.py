"""Tests for RetailAsk Business Graph construction and traversal (Step 3B)."""

from __future__ import annotations

import unittest

from business_graph import (
    BusinessGraphBuilder,
    BusinessGraphService,
    NodeLabel,
    RelType,
)
from business_graph.seed_fixture import seed_records


class BusinessGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        builder = BusinessGraphBuilder()
        cls.stats = builder.build_from_records(**seed_records())
        cls.store = builder.store
        cls.service = BusinessGraphService(cls.store)

    def test_node_counts(self):
        self.assertEqual(self.stats.node_count, 5 + 6 + 8 + 24 + 24 + 15)
        self.assertEqual(
            self.stats.node_types,
            {
                'Brand': 5,
                'Category': 6,
                'CustomerFeedback': 15,
                'Issue': 8,
                'Product': 24,
                'Sale': 24,
            },
        )

    def test_relationship_counts(self):
        # 24 brand→product + 24 category→product + 24 product→sale
        # + 15 product→feedback + 10 feedback→issue (nullable issue_id skipped)
        self.assertEqual(self.stats.relationship_count, 24 + 24 + 24 + 15 + 10)
        self.assertEqual(
            self.stats.relationship_types,
            {
                'ABOUT_ISSUE': 10,
                'HAS_FEEDBACK': 15,
                'HAS_PRODUCT': 48,
                'HAS_SALE': 24,
            },
        )

    def test_mysql_ids_preserved_on_nodes(self):
        product = self.service.get_product(6)
        self.assertIsNotNone(product)
        self.assertEqual(product.key, 'Product:6')
        self.assertEqual(product.properties['product_id'], 6)
        self.assertEqual(product.properties['product_name'], 'Mouse')
        self.assertEqual(product.properties['brand_id'], 4)
        self.assertEqual(product.properties['category_id'], 4)

    def test_get_product_sales(self):
        sales = self.service.get_product_sales(6)
        self.assertEqual(len(sales), 3)  # sale_ids 6, 22, 24
        quantities = sorted(int(s.properties['quantity']) for s in sales)
        self.assertEqual(quantities, [20, 20, 30])

    def test_get_product_feedback_and_issues(self):
        feedback = self.service.get_product_feedback(6)
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0].properties['sentiment'], 'negative')
        issues = self.service.get_product_issues(6)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].properties['issue_name'], 'Compatibility')

    def test_get_products_by_brand_and_category(self):
        powerlink = self.service.get_products_by_brand(4)
        names = {p.properties['product_name'] for p in powerlink}
        self.assertIn('Mouse', names)
        self.assertIn('Keyboard', names)

        accessories = self.service.get_products_by_category(4)
        acc_names = {p.properties['product_name'] for p in accessories}
        self.assertIn('Mouse', acc_names)
        self.assertIn('Webcam', acc_names)

    def test_only_fk_backed_about_issue_edges(self):
        """Feedback without issue_id must not invent ABOUT_ISSUE edges."""
        feedback = self.service.get_product_feedback(2)  # Smartphone positive, issue_id NULL
        self.assertEqual(len(feedback), 1)
        neighbors = self.store.get_neighbors(
            feedback[0].key, rel_type=RelType.ABOUT_ISSUE, direction='out'
        )
        self.assertEqual(neighbors, [])

    def test_headphones_summary_has_return(self):
        report = self.service.format_product_report(3)
        self.assertIn('Product: Headphones', report)
        self.assertIn('Brand: SoundMax', report)
        self.assertIn('Category: Audio', report)
        self.assertIn('Issue: Durability', report)
        self.assertIn('Return: yes', report)

    def test_idempotent_rebuild_in_memory(self):
        builder = BusinessGraphBuilder()
        first = builder.build_from_records(**seed_records())
        second = builder.build_from_records(**seed_records(), clear_existing=False)
        self.assertEqual(first.node_count, second.node_count)
        self.assertEqual(first.relationship_count, second.relationship_count)


if __name__ == '__main__':
    unittest.main()
