#!/usr/bin/env python3
"""
Demo / inspection for RetailAsk Business Graph (Step 3B).

Builds the graph from MySQL when available, otherwise from seed_fixture
(matching Backend/seed.sql). Does NOT call Schema RAG, Qwen, or agents.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from business_graph import BusinessGraphBuilder, BusinessGraphService
from business_graph.seed_fixture import seed_records

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)
logger = logging.getLogger('retail-agent')


def build_graph(prefer_mysql: bool = True):
    builder = BusinessGraphBuilder()
    if prefer_mysql:
        try:
            from dotenv import load_dotenv

            load_dotenv(BACKEND_DIR / '.env', override=True)
            from app import get_db_connection

            stats = builder.build_from_mysql(get_db_connection)
            logger.info('Business graph source | MySQL')
            return builder.store, stats, 'mysql'
        except Exception as exc:
            logger.warning('MySQL build failed, using seed fixture | %s', exc)

    records = seed_records()
    stats = builder.build_from_records(**records)
    logger.info('Business graph source | seed_fixture')
    return builder.store, stats, 'seed_fixture'


def main() -> int:
    parser = argparse.ArgumentParser(description='RetailAsk Business Graph demo')
    parser.add_argument(
        '--product-id',
        type=int,
        default=6,
        help='Product id to inspect (default: 6 = Mouse from seed)',
    )
    parser.add_argument(
        '--seed-only',
        action='store_true',
        help='Skip MySQL and build from seed_fixture only',
    )
    args = parser.parse_args()

    store, stats, source = build_graph(prefer_mysql=not args.seed_only)
    service = BusinessGraphService(store)

    print('=' * 72)
    print('RetailAsk Business Graph demo (Step 3B)')
    print(f'Source: {source}')
    print(f"Storage: {stats.storage}")
    print(f'Nodes: {stats.node_count}')
    print(f'Relationships: {stats.relationship_count}')
    print(f'Node types: {stats.node_types}')
    print(f'Relationship types: {stats.relationship_types}')
    print('=' * 72)

    print('\nTraversal helpers:')
    product = service.get_product(args.product_id)
    if product is None:
        print(f'  Product {args.product_id} not found')
        return 1

    brand_products = []
    brand_id = product.properties.get('brand_id')
    if brand_id is not None:
        brand_products = service.get_products_by_brand(int(brand_id))

    category_products = []
    category_id = product.properties.get('category_id')
    if category_id is not None:
        category_products = service.get_products_by_category(int(category_id))

    print(f"  get_product({args.product_id}) -> {product.properties.get('product_name')}")
    print(f'  get_product_sales -> {len(service.get_product_sales(args.product_id))} sale node(s)')
    print(
        f'  get_product_feedback -> {len(service.get_product_feedback(args.product_id))} feedback node(s)'
    )
    print(
        f'  get_product_issues -> '
        f"{[i.properties.get('issue_name') for i in service.get_product_issues(args.product_id)]}"
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
    print(service.format_product_report(args.product_id))
    print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
