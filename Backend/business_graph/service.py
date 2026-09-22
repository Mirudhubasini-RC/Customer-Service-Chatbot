"""Traversal helpers over the RetailAsk business graph."""

from __future__ import annotations

from typing import Any

from .models import GraphNode, NodeLabel, RelType, node_key
from .store import GraphStore


class BusinessGraphService:
    """Read API for business-graph inspection / future Graph RAG."""

    def __init__(self, store: GraphStore):
        self.store = store

    def get_product(self, product_id: int) -> GraphNode | None:
        return self.store.get_node(node_key(NodeLabel.PRODUCT, product_id))

    def get_product_sales(self, product_id: int) -> list[GraphNode]:
        product_key = node_key(NodeLabel.PRODUCT, product_id)
        return [
            neighbor
            for _, neighbor in self.store.get_neighbors(
                product_key, rel_type=RelType.HAS_SALE, direction='out'
            )
        ]

    def get_product_feedback(self, product_id: int) -> list[GraphNode]:
        product_key = node_key(NodeLabel.PRODUCT, product_id)
        return [
            neighbor
            for _, neighbor in self.store.get_neighbors(
                product_key, rel_type=RelType.HAS_FEEDBACK, direction='out'
            )
        ]

    def get_product_issues(self, product_id: int) -> list[GraphNode]:
        """Issues linked via Product → CustomerFeedback → Issue (deduped)."""
        seen: set[str] = set()
        issues: list[GraphNode] = []
        for feedback in self.get_product_feedback(product_id):
            for _, issue in self.store.get_neighbors(
                feedback.key, rel_type=RelType.ABOUT_ISSUE, direction='out'
            ):
                if issue.key not in seen:
                    seen.add(issue.key)
                    issues.append(issue)
        return issues

    def get_products_by_brand(self, brand_id: int) -> list[GraphNode]:
        brand_key = node_key(NodeLabel.BRAND, brand_id)
        return [
            neighbor
            for _, neighbor in self.store.get_neighbors(
                brand_key, rel_type=RelType.HAS_PRODUCT, direction='out'
            )
        ]

    def get_products_by_category(self, category_id: int) -> list[GraphNode]:
        category_key = node_key(NodeLabel.CATEGORY, category_id)
        return [
            neighbor
            for _, neighbor in self.store.get_neighbors(
                category_key, rel_type=RelType.HAS_PRODUCT, direction='out'
            )
        ]

    def get_product_brand(self, product_id: int) -> GraphNode | None:
        product = self.get_product(product_id)
        if not product:
            return None
        brand_id = product.properties.get('brand_id')
        if brand_id is None:
            return None
        return self.store.get_node(node_key(NodeLabel.BRAND, int(brand_id)))

    def get_product_category(self, product_id: int) -> GraphNode | None:
        product = self.get_product(product_id)
        if not product:
            return None
        category_id = product.properties.get('category_id')
        if category_id is None:
            return None
        return self.store.get_node(node_key(NodeLabel.CATEGORY, int(category_id)))

    def summarize_product(self, product_id: int) -> dict[str, Any] | None:
        """Inspection-friendly nested summary for demos."""
        product = self.get_product(product_id)
        if product is None:
            return None

        brand = self.get_product_brand(product_id)
        category = self.get_product_category(product_id)
        sales = self.get_product_sales(product_id)
        feedback_nodes = self.get_product_feedback(product_id)

        total_units = sum(int(s.properties.get('quantity') or 0) for s in sales)
        total_revenue = sum(float(s.properties.get('total_price') or 0) for s in sales)

        feedback_summaries = []
        for fb in feedback_nodes:
            issue_name = None
            neighbors = self.store.get_neighbors(
                fb.key, rel_type=RelType.ABOUT_ISSUE, direction='out'
            )
            if neighbors:
                issue_name = neighbors[0][1].properties.get('issue_name')
            feedback_summaries.append(
                {
                    'feedback_id': fb.properties.get('feedback_id'),
                    'sentiment': fb.properties.get('sentiment'),
                    'issue': issue_name,
                    'is_return': bool(fb.properties.get('is_return')),
                    'return_reason': fb.properties.get('return_reason'),
                    'feedback_text': fb.properties.get('feedback_text'),
                }
            )

        return {
            'product_id': product.properties.get('product_id'),
            'product_name': product.properties.get('product_name'),
            'price': product.properties.get('price'),
            'brand': brand.properties.get('brand_name') if brand else None,
            'category': category.properties.get('category_name') if category else None,
            'sales_units': total_units,
            'sales_revenue': total_revenue,
            'sales_count': len(sales),
            'feedback': feedback_summaries,
            'issues': [
                i.properties.get('issue_name') for i in self.get_product_issues(product_id)
            ],
        }

    def format_product_report(self, product_id: int) -> str:
        summary = self.summarize_product(product_id)
        if summary is None:
            return f'Product id={product_id} not found in graph.'

        lines = [
            f"Product: {summary['product_name']}",
            f"  Brand: {summary['brand'] or 'n/a'}",
            f"  Category: {summary['category'] or 'n/a'}",
            f"  Sales: {summary['sales_units']} units "
            f"(across {summary['sales_count']} sale row(s), "
            f"revenue={summary['sales_revenue']:.2f})",
            '  Feedback:',
        ]
        if not summary['feedback']:
            lines.append('    - (none)')
        for item in summary['feedback']:
            lines.append(f"    - {item['sentiment']}")
            lines.append(f"      Issue: {item['issue'] or 'n/a'}")
            lines.append(
                f"      Return: {'yes' if item['is_return'] else 'no'}"
                + (
                    f" ({item['return_reason']})"
                    if item['is_return'] and item['return_reason']
                    else ''
                )
            )
            if item.get('feedback_text'):
                lines.append(f"      Text: {item['feedback_text']}")
        return '\n'.join(lines)
