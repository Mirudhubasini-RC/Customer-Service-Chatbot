#!/usr/bin/env python3
"""
Demo / inspection for RetailAsk Business Graph (Step 3B).

Modes:
  default / --seed-only  → InMemoryGraphStore (offline / tests)
  --neo4j                → Neo4jGraphStore (sync from MySQL or seed_fixture)

Does NOT call Schema RAG, Qwen, or agents.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / '.env', override=True)

from business_graph import (
    BusinessGraphBuilder,
    BusinessGraphService,
    InMemoryGraphStore,
    Neo4jGraphStore,
)
from business_graph.seed_fixture import seed_records

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)
logger = logging.getLogger('retail-agent')

CYPHER_PRODUCT_FEEDBACK = """
MATCH (p:Product {product_id: $product_id})
OPTIONAL MATCH (b:Brand)-[:HAS_PRODUCT]->(p)
OPTIONAL MATCH (c:Category)-[:HAS_PRODUCT]->(p)
OPTIONAL MATCH (p)-[:HAS_FEEDBACK]->(f:CustomerFeedback)
OPTIONAL MATCH (f)-[:ABOUT_ISSUE]->(i:Issue)
RETURN p.product_name AS product,
       b.brand_name AS brand,
       c.category_name AS category,
       f.sentiment AS sentiment,
       f.is_return AS is_return,
       f.return_reason AS return_reason,
       i.issue_name AS issue
ORDER BY sentiment
"""


def build_into_store(store, prefer_mysql: bool):
    builder = BusinessGraphBuilder(store=store)
    if prefer_mysql:
        try:
            from app import get_db_connection

            stats = builder.build_from_mysql(get_db_connection)
            return stats, 'mysql'
        except Exception as exc:
            logger.warning('MySQL build failed, using seed fixture | %s', exc)
    stats = builder.build_from_records(**seed_records())
    return stats, 'seed_fixture'


def print_report(service: BusinessGraphService, product_id: int) -> int:
    product = service.get_product(product_id)
    if product is None:
        print(f'  Product {product_id} not found')
        return 1

    brand_id = product.properties.get('brand_id')
    category_id = product.properties.get('category_id')
    brand_products = (
        service.get_products_by_brand(int(brand_id)) if brand_id is not None else []
    )
    category_products = (
        service.get_products_by_category(int(category_id))
        if category_id is not None
        else []
    )

    print('\nTraversal helpers (via GraphStore):')
    print(f"  get_product({product_id}) -> {product.properties.get('product_name')}")
    print(f'  get_product_sales -> {len(service.get_product_sales(product_id))} sale node(s)')
    print(
        f'  get_product_feedback -> {len(service.get_product_feedback(product_id))} feedback node(s)'
    )
    print(
        f'  get_product_issues -> '
        f"{[i.properties.get('issue_name') for i in service.get_product_issues(product_id)]}"
    )
    print(
        f'  get_products_by_brand({brand_id}) -> '
        f"{[p.properties.get('product_name') for p in brand_products]}"
    )
    print(
        f'  get_products_by_category({category_id}) -> '
        f"{[p.properties.get('product_name') for p in category_products]}"
    )

    print('\nProduct inspection report:')
    print(service.format_product_report(product_id))
    return 0


def print_cypher_demo(store: Neo4jGraphStore, product_id: int) -> None:
    print('\nCypher inspection (products ↔ feedback ↔ issues):')
    rows = store.run_cypher(CYPHER_PRODUCT_FEEDBACK, {'product_id': product_id})
    if not rows:
        print('  (no rows)')
        return
    for row in rows:
        print(
            f"  product={row.get('product')} | brand={row.get('brand')} | "
            f"category={row.get('category')} | sentiment={row.get('sentiment')} | "
            f"issue={row.get('issue')} | return={row.get('is_return')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description='RetailAsk Business Graph demo')
    parser.add_argument(
        '--product-id',
        type=int,
        default=3,
        help='Product id to inspect (default: 3 = Headphones)',
    )
    parser.add_argument(
        '--seed-only',
        action='store_true',
        help='Use InMemoryGraphStore + seed_fixture (skip MySQL)',
    )
    parser.add_argument(
        '--neo4j',
        action='store_true',
        help='Use Neo4jGraphStore; sync from MySQL (or seed_fixture if MySQL fails)',
    )
    args = parser.parse_args()

    store = None
    try:
        if args.neo4j:
            store = Neo4jGraphStore.from_env()
            stats, source = build_into_store(store, prefer_mysql=not args.seed_only)
            storage_name = 'Neo4jGraphStore'
        else:
            store = InMemoryGraphStore()
            stats, source = build_into_store(store, prefer_mysql=not args.seed_only)
            storage_name = 'InMemoryGraphStore'

        service = BusinessGraphService(store)

        print('=' * 72)
        print('RetailAsk Business Graph demo (Step 3B)')
        print(f'Source: {source}')
        print(f'Storage: {storage_name}')
        print(f'Nodes: {stats.node_count}')
        print(f'Relationships: {stats.relationship_count}')
        print(f'Node types: {stats.node_types}')
        print(f'Relationship types: {stats.relationship_types}')
        print('=' * 72)

        code = print_report(service, args.product_id)
        if args.neo4j and isinstance(store, Neo4jGraphStore):
            print_cypher_demo(store, args.product_id)
        print()
        return code
    finally:
        if isinstance(store, Neo4jGraphStore):
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
