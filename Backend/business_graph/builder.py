"""
Build the RetailAsk business graph from MySQL rows (or injected record dicts).

Only creates relationships backed by real FKs:
  products.brand_id, products.category_id,
  sales.product_id,
  customer_feedback.product_id, customer_feedback.issue_id
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from .models import GraphNode, GraphRelationship, NodeLabel, RelType, node_key
from .store import GraphStore, InMemoryGraphStore

logger = logging.getLogger('retail-agent')


@dataclass
class BuildStats:
    node_count: int
    relationship_count: int
    node_types: dict[str, int]
    relationship_types: dict[str, int]
    storage: str

    def as_dict(self) -> dict[str, Any]:
        return {
            'node_count': self.node_count,
            'relationship_count': self.relationship_count,
            'node_types': self.node_types,
            'relationship_types': self.relationship_types,
            'storage': self.storage,
        }


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return value


def _row(props: dict[str, Any]) -> dict[str, Any]:
    return {k: _serialize(v) for k, v in props.items()}


class BusinessGraphBuilder:
    """Construct graph nodes/edges from RetailAsk relational data."""

    def __init__(self, store: GraphStore | None = None):
        self.store = store or InMemoryGraphStore()

    def build_from_records(
        self,
        *,
        brands: list[dict[str, Any]],
        categories: list[dict[str, Any]],
        issues: list[dict[str, Any]],
        products: list[dict[str, Any]],
        sales: list[dict[str, Any]],
        customer_feedback: list[dict[str, Any]],
    ) -> BuildStats:
        self.store.clear()

        for brand in brands:
            brand_id = int(brand['brand_id'])
            self.store.upsert_node(
                GraphNode(
                    key=node_key(NodeLabel.BRAND, brand_id),
                    label=NodeLabel.BRAND,
                    properties=_row(
                        {
                            'brand_id': brand_id,
                            'brand_name': brand.get('brand_name'),
                        }
                    ),
                )
            )

        for category in categories:
            category_id = int(category['category_id'])
            self.store.upsert_node(
                GraphNode(
                    key=node_key(NodeLabel.CATEGORY, category_id),
                    label=NodeLabel.CATEGORY,
                    properties=_row(
                        {
                            'category_id': category_id,
                            'category_name': category.get('category_name'),
                        }
                    ),
                )
            )

        for issue in issues:
            issue_id = int(issue['issue_id'])
            self.store.upsert_node(
                GraphNode(
                    key=node_key(NodeLabel.ISSUE, issue_id),
                    label=NodeLabel.ISSUE,
                    properties=_row(
                        {
                            'issue_id': issue_id,
                            'issue_name': issue.get('issue_name'),
                        }
                    ),
                )
            )

        for product in products:
            product_id = int(product['product_id'])
            brand_id = product.get('brand_id')
            category_id = product.get('category_id')
            product_key = node_key(NodeLabel.PRODUCT, product_id)
            self.store.upsert_node(
                GraphNode(
                    key=product_key,
                    label=NodeLabel.PRODUCT,
                    properties=_row(
                        {
                            'product_id': product_id,
                            'product_name': product.get('product_name'),
                            'price': product.get('price'),
                            'brand_id': brand_id,
                            'category_id': category_id,
                        }
                    ),
                )
            )
            if brand_id is not None:
                self.store.upsert_relationship(
                    GraphRelationship(
                        start_key=node_key(NodeLabel.BRAND, int(brand_id)),
                        rel_type=RelType.HAS_PRODUCT,
                        end_key=product_key,
                    )
                )
            if category_id is not None:
                self.store.upsert_relationship(
                    GraphRelationship(
                        start_key=node_key(NodeLabel.CATEGORY, int(category_id)),
                        rel_type=RelType.HAS_PRODUCT,
                        end_key=product_key,
                    )
                )

        for sale in sales:
            sale_id = int(sale['sale_id'])
            product_id = sale.get('product_id')
            sale_key = node_key(NodeLabel.SALE, sale_id)
            self.store.upsert_node(
                GraphNode(
                    key=sale_key,
                    label=NodeLabel.SALE,
                    properties=_row(
                        {
                            'sale_id': sale_id,
                            'product_id': product_id,
                            'sale_date': sale.get('sale_date'),
                            'quantity': sale.get('quantity'),
                            'total_price': sale.get('total_price'),
                        }
                    ),
                )
            )
            if product_id is not None:
                self.store.upsert_relationship(
                    GraphRelationship(
                        start_key=node_key(NodeLabel.PRODUCT, int(product_id)),
                        rel_type=RelType.HAS_SALE,
                        end_key=sale_key,
                    )
                )

        for feedback in customer_feedback:
            feedback_id = int(feedback['feedback_id'])
            product_id = feedback.get('product_id')
            issue_id = feedback.get('issue_id')
            feedback_key = node_key(NodeLabel.CUSTOMER_FEEDBACK, feedback_id)
            self.store.upsert_node(
                GraphNode(
                    key=feedback_key,
                    label=NodeLabel.CUSTOMER_FEEDBACK,
                    properties=_row(
                        {
                            'feedback_id': feedback_id,
                            'product_id': product_id,
                            'issue_id': issue_id,
                            'feedback_text': feedback.get('feedback_text'),
                            'sentiment': feedback.get('sentiment'),
                            'is_return': bool(feedback.get('is_return')),
                            'return_reason': feedback.get('return_reason'),
                            'feedback_date': feedback.get('feedback_date'),
                        }
                    ),
                )
            )
            if product_id is not None:
                self.store.upsert_relationship(
                    GraphRelationship(
                        start_key=node_key(NodeLabel.PRODUCT, int(product_id)),
                        rel_type=RelType.HAS_FEEDBACK,
                        end_key=feedback_key,
                    )
                )
            if issue_id is not None:
                self.store.upsert_relationship(
                    GraphRelationship(
                        start_key=feedback_key,
                        rel_type=RelType.ABOUT_ISSUE,
                        end_key=node_key(NodeLabel.ISSUE, int(issue_id)),
                    )
                )

        stats = self.store.stats()
        build_stats = BuildStats(
            node_count=stats['node_count'],
            relationship_count=stats['relationship_count'],
            node_types=stats['node_types'],
            relationship_types=stats['relationship_types'],
            storage=stats['storage'],
        )
        logger.info(
            'Business graph built | nodes=%s | relationships=%s | node_types=%s | '
            'relationship_types=%s | storage=%s',
            build_stats.node_count,
            build_stats.relationship_count,
            build_stats.node_types,
            build_stats.relationship_types,
            build_stats.storage,
        )
        return build_stats

    def build_from_mysql(
        self,
        connection_factory: Callable[[], Any],
    ) -> BuildStats:
        """
        Read current MySQL tables and build the graph.

        connection_factory: zero-arg callable returning a DB-API connection
        (e.g. app.get_db_connection).
        """
        conn = connection_factory()
        cursor = conn.cursor(dictionary=True)
        try:
            def fetch(sql: str) -> list[dict[str, Any]]:
                cursor.execute(sql)
                return list(cursor.fetchall() or [])

            brands = fetch('SELECT brand_id, brand_name FROM brands')
            categories = fetch('SELECT category_id, category_name FROM categories')
            issues = fetch('SELECT issue_id, issue_name FROM issues')
            products = fetch(
                'SELECT product_id, product_name, price, brand_id, category_id FROM products'
            )
            sales = fetch(
                'SELECT sale_id, product_id, sale_date, quantity, total_price FROM sales'
            )
            feedback = fetch(
                'SELECT feedback_id, product_id, issue_id, feedback_text, sentiment, '
                'is_return, return_reason, feedback_date FROM customer_feedback'
            )
        finally:
            cursor.close()
            conn.close()

        return self.build_from_records(
            brands=brands,
            categories=categories,
            issues=issues,
            products=products,
            sales=sales,
            customer_feedback=feedback,
        )
