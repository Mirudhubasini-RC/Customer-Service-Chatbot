"""
Neo4j integration tests for RetailAsk Business Graph.

Requires a running Neo4j instance and env:
  NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, optional NEO4J_DATABASE

Skip automatically when Neo4j is not configured / unreachable.

Run:
  python -m unittest tests.test_business_graph_neo4j -v
"""

from __future__ import annotations

import os
import unittest

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

from business_graph import BusinessGraphBuilder, BusinessGraphService, Neo4jGraphStore
from business_graph.seed_fixture import seed_records


def _neo4j_available() -> bool:
    if not (os.getenv('NEO4J_URI') or '').strip():
        return False
    if not (os.getenv('NEO4J_USERNAME') or os.getenv('NEO4J_USER') or '').strip():
        return False
    if os.getenv('NEO4J_PASSWORD') is None:
        return False
    try:
        store = Neo4jGraphStore.from_env(ensure_schema=True)
        store.close()
        return True
    except Exception:
        return False


@unittest.skipUnless(_neo4j_available(), 'Neo4j not configured or unreachable')
class Neo4jBusinessGraphIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Neo4jGraphStore.from_env(ensure_schema=True)
        cls.builder = BusinessGraphBuilder(store=cls.store)
        cls.stats = cls.builder.build_from_records(**seed_records())
        cls.service = BusinessGraphService(cls.store)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.store.clear()
        finally:
            cls.store.close()

    def test_node_and_relationship_counts(self):
        self.assertEqual(self.stats.node_count, 82)
        self.assertEqual(self.stats.relationship_count, 97)
        self.assertEqual(self.stats.storage, 'Neo4jGraphStore')

    def test_traversal_headphones(self):
        product = self.service.get_product(3)
        self.assertIsNotNone(product)
        self.assertEqual(product.properties['product_name'], 'Headphones')
        issues = self.service.get_product_issues(3)
        self.assertIn('Durability', [i.properties['issue_name'] for i in issues])
        report = self.service.format_product_report(3)
        self.assertIn('Brand: SoundMax', report)
        self.assertIn('Return: yes', report)

    def test_idempotent_rebuild(self):
        """Running the builder twice must not duplicate nodes/relationships."""
        # Second sync without clearing — relies on Neo4j MERGE
        second = self.builder.build_from_records(**seed_records(), clear_existing=False)
        self.assertEqual(second.node_count, self.stats.node_count)
        self.assertEqual(second.relationship_count, self.stats.relationship_count)
        live = self.store.stats()
        self.assertEqual(live['node_count'], 82)
        self.assertEqual(live['relationship_count'], 97)


if __name__ == '__main__':
    unittest.main()
