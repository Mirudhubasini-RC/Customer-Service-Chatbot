"""
Business Graph Retrieval (Step 3C).

Question → structured intent → Cypher against Neo4j → normalized graph context.

Does NOT call Qwen. Does NOT replace Schema RAG / SQL. Not full Graph RAG yet.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from .intent import (
    BRAND_PRODUCTS,
    BRANDS_WITH_NEGATIVE_FEEDBACK,
    CATEGORY_PRODUCTS,
    PRODUCT_CONTEXT,
    PRODUCT_FEEDBACK,
    PRODUCT_ISSUES,
    QUALITY_ISSUE_NAMES,
    PRODUCT_SALES,
    PRODUCTS_HIGH_SALES_AND_QUALITY_ISSUES,
    PRODUCTS_NEGATIVE_FEEDBACK_RETURNS,
    PRODUCTS_WITH_QUALITY_ISSUES,
    UNSUPPORTED,
    RetrievalIntent,
    parse_retrieval_intent,
)

logger = logging.getLogger('retail-agent')


class CypherRunner(Protocol):
    """Minimal protocol satisfied by Neo4jGraphStore."""

    def run_cypher(
        self, cypher: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        ...


def empty_context(question: str, intent: RetrievalIntent | None = None) -> dict[str, Any]:
    return {
        'question': question,
        'intent': intent.as_dict() if intent else None,
        'nodes': [],
        'relationships': [],
        'facts': [],
        'source': 'neo4j',
    }


class GraphRetriever:
    """
    Retrieve relationship-shaped retail facts from Neo4j Aura.

    Structured methods are Cypher-backed. High-level `retrieve(question)`
    parses a deterministic intent, then executes the matching Cypher plan.
    """

    def __init__(self, store: CypherRunner):
        self.store = store

    # ------------------------------------------------------------------
    # Structured retrieval methods
    # ------------------------------------------------------------------

    def retrieve_product_context(self, product_id: int) -> dict[str, Any]:
        rows = self.store.run_cypher(
            """
            MATCH (p:Product {product_id: $product_id})
            OPTIONAL MATCH (b:Brand)-[:HAS_PRODUCT]->(p)
            OPTIONAL MATCH (c:Category)-[:HAS_PRODUCT]->(p)
            OPTIONAL MATCH (p)-[:HAS_SALE]->(s:Sale)
            OPTIONAL MATCH (p)-[:HAS_FEEDBACK]->(f:CustomerFeedback)
            OPTIONAL MATCH (f)-[:ABOUT_ISSUE]->(i:Issue)
            RETURN p, b, c, collect(DISTINCT s) AS sales,
                   collect(DISTINCT f) AS feedbacks,
                   collect(DISTINCT i) AS issues
            """,
            {'product_id': int(product_id)},
        )
        return self._context_from_product_bundle(
            question=f'product_context:{product_id}',
            intent=RetrievalIntent(
                intent_type=PRODUCT_CONTEXT,
                entities=['Brand', 'Product', 'Category', 'Sale', 'CustomerFeedback', 'Issue'],
                relationships=[
                    'Brand-HAS_PRODUCT->Product',
                    'Category-HAS_PRODUCT->Product',
                    'Product-HAS_SALE->Sale',
                    'Product-HAS_FEEDBACK->CustomerFeedback',
                    'CustomerFeedback-ABOUT_ISSUE->Issue',
                ],
                product_id=product_id,
            ),
            rows=rows,
        )

    def retrieve_product_feedback(self, product_id: int) -> dict[str, Any]:
        rows = self.store.run_cypher(
            """
            MATCH (p:Product {product_id: $product_id})-[:HAS_FEEDBACK]->(f:CustomerFeedback)
            OPTIONAL MATCH (f)-[:ABOUT_ISSUE]->(i:Issue)
            RETURN p, f, i
            ORDER BY f.feedback_id
            """,
            {'product_id': int(product_id)},
        )
        intent = RetrievalIntent(
            intent_type=PRODUCT_FEEDBACK,
            entities=['Product', 'CustomerFeedback', 'Issue'],
            relationships=[
                'Product-HAS_FEEDBACK->CustomerFeedback',
                'CustomerFeedback-ABOUT_ISSUE->Issue',
            ],
            product_id=product_id,
        )
        return self._context_from_feedback_rows(
            question=f'product_feedback:{product_id}',
            intent=intent,
            rows=rows,
        )

    def retrieve_product_sales(self, product_id: int) -> dict[str, Any]:
        rows = self.store.run_cypher(
            """
            MATCH (p:Product {product_id: $product_id})-[:HAS_SALE]->(s:Sale)
            RETURN p, s
            ORDER BY s.sale_date
            """,
            {'product_id': int(product_id)},
        )
        intent = RetrievalIntent(
            intent_type=PRODUCT_SALES,
            entities=['Product', 'Sale'],
            relationships=['Product-HAS_SALE->Sale'],
            product_id=product_id,
        )
        ctx = empty_context(f'product_sales:{product_id}', intent)
        if not rows:
            return ctx
        product = self._node_props(rows[0].get('p'), 'Product')
        self._add_node(ctx, product)
        total_qty = 0
        total_rev = 0.0
        for row in rows:
            sale = self._node_props(row.get('s'), 'Sale')
            if not sale:
                continue
            self._add_node(ctx, sale)
            self._add_rel(ctx, product['key'], 'HAS_SALE', sale['key'])
            total_qty += int(sale.get('quantity') or 0)
            total_rev += float(sale.get('total_price') or 0)
        ctx['facts'].append(
            {
                'type': 'product_sales_summary',
                'product_id': product_id,
                'product_name': product.get('product_name'),
                'sales_units': total_qty,
                'sales_revenue': total_rev,
                'sale_rows': len(rows),
            }
        )
        return ctx

    def retrieve_product_issues(self, product_id: int) -> dict[str, Any]:
        rows = self.store.run_cypher(
            """
            MATCH (p:Product {product_id: $product_id})-[:HAS_FEEDBACK]->(f:CustomerFeedback)
                  -[:ABOUT_ISSUE]->(i:Issue)
            RETURN p, f, i
            ORDER BY i.issue_name
            """,
            {'product_id': int(product_id)},
        )
        intent = RetrievalIntent(
            intent_type=PRODUCT_ISSUES,
            entities=['Product', 'CustomerFeedback', 'Issue'],
            relationships=[
                'Product-HAS_FEEDBACK->CustomerFeedback',
                'CustomerFeedback-ABOUT_ISSUE->Issue',
            ],
            product_id=product_id,
        )
        return self._context_from_feedback_rows(
            question=f'product_issues:{product_id}',
            intent=intent,
            rows=rows,
        )

    def retrieve_brand_products(self, brand_id: int) -> dict[str, Any]:
        rows = self.store.run_cypher(
            """
            MATCH (b:Brand {brand_id: $brand_id})-[:HAS_PRODUCT]->(p:Product)
            RETURN b, p
            ORDER BY p.product_name
            """,
            {'brand_id': int(brand_id)},
        )
        intent = RetrievalIntent(
            intent_type=BRAND_PRODUCTS,
            entities=['Brand', 'Product'],
            relationships=['Brand-HAS_PRODUCT->Product'],
            brand_id=brand_id,
        )
        ctx = empty_context(f'brand_products:{brand_id}', intent)
        for row in rows:
            brand = self._node_props(row.get('b'), 'Brand')
            product = self._node_props(row.get('p'), 'Product')
            if brand:
                self._add_node(ctx, brand)
            if product:
                self._add_node(ctx, product)
                if brand:
                    self._add_rel(ctx, brand['key'], 'HAS_PRODUCT', product['key'])
                    ctx['facts'].append(
                        {
                            'type': 'brand_has_product',
                            'brand': brand.get('brand_name'),
                            'product': product.get('product_name'),
                            'product_id': product.get('product_id'),
                        }
                    )
        return ctx

    def retrieve_category_products(self, category_id: int) -> dict[str, Any]:
        rows = self.store.run_cypher(
            """
            MATCH (c:Category {category_id: $category_id})-[:HAS_PRODUCT]->(p:Product)
            RETURN c, p
            ORDER BY p.product_name
            """,
            {'category_id': int(category_id)},
        )
        intent = RetrievalIntent(
            intent_type=CATEGORY_PRODUCTS,
            entities=['Category', 'Product'],
            relationships=['Category-HAS_PRODUCT->Product'],
            category_id=category_id,
        )
        ctx = empty_context(f'category_products:{category_id}', intent)
        for row in rows:
            category = self._node_props(row.get('c'), 'Category')
            product = self._node_props(row.get('p'), 'Product')
            if category:
                self._add_node(ctx, category)
            if product:
                self._add_node(ctx, product)
                if category:
                    self._add_rel(ctx, category['key'], 'HAS_PRODUCT', product['key'])
                    ctx['facts'].append(
                        {
                            'type': 'category_has_product',
                            'category': category.get('category_name'),
                            'product': product.get('product_name'),
                            'product_id': product.get('product_id'),
                        }
                    )
        return ctx

    # ------------------------------------------------------------------
    # High-level NL retrieval
    # ------------------------------------------------------------------

    def retrieve(self, question: str) -> dict[str, Any]:
        intent = parse_retrieval_intent(question)
        logger.info(
            'Graph retrieval intent | question=%s | intent=%s | filters=%s',
            question,
            intent.intent_type,
            intent.filters,
        )

        if intent.intent_type == UNSUPPORTED:
            ctx = empty_context(question, intent)
            ctx['facts'].append(
                {
                    'type': 'unsupported',
                    'message': 'No matching business-graph retrieval pattern for this question.',
                    'reason': intent.filters.get('reason'),
                }
            )
            return ctx

        if intent.intent_type == PRODUCT_CONTEXT and intent.product_id is not None:
            ctx = self.retrieve_product_context(intent.product_id)
            ctx['question'] = question
            return ctx
        if intent.intent_type == PRODUCT_SALES and intent.product_id is not None:
            ctx = self.retrieve_product_sales(intent.product_id)
            ctx['question'] = question
            return ctx
        if intent.intent_type == PRODUCT_FEEDBACK and intent.product_id is not None:
            ctx = self.retrieve_product_feedback(intent.product_id)
            ctx['question'] = question
            return ctx
        if intent.intent_type == PRODUCT_ISSUES and intent.product_id is not None:
            ctx = self.retrieve_product_issues(intent.product_id)
            ctx['question'] = question
            return ctx
        if intent.intent_type == BRAND_PRODUCTS and intent.brand_id is not None:
            ctx = self.retrieve_brand_products(intent.brand_id)
            ctx['question'] = question
            return ctx
        if intent.intent_type == CATEGORY_PRODUCTS and intent.category_id is not None:
            ctx = self.retrieve_category_products(intent.category_id)
            ctx['question'] = question
            return ctx

        if intent.intent_type == PRODUCTS_WITH_QUALITY_ISSUES:
            return self._retrieve_products_with_quality_issues(question, intent)
        if intent.intent_type == PRODUCTS_NEGATIVE_FEEDBACK_RETURNS:
            return self._retrieve_products_negative_feedback_returns(question, intent)
        if intent.intent_type == BRANDS_WITH_NEGATIVE_FEEDBACK:
            return self._retrieve_brands_with_negative_feedback(question, intent)
        if intent.intent_type == PRODUCTS_HIGH_SALES_AND_QUALITY_ISSUES:
            return self._retrieve_products_high_sales_and_quality_issues(question, intent)

        return empty_context(question, intent)

    # ------------------------------------------------------------------
    # Cypher plans for relationship-oriented questions
    # ------------------------------------------------------------------

    def _quality_issue_params(self, intent: RetrievalIntent) -> dict[str, Any]:
        names = intent.filters.get('quality_issue_names') or list(QUALITY_ISSUE_NAMES)
        return {'quality_issue_names': list(names)}

    def _retrieve_products_with_quality_issues(
        self, question: str, intent: RetrievalIntent
    ) -> dict[str, Any]:
        params = self._quality_issue_params(intent)
        rows = self.store.run_cypher(
            """
            MATCH (p:Product)-[:HAS_FEEDBACK]->(f:CustomerFeedback)-[:ABOUT_ISSUE]->(i:Issue)
            WHERE i.issue_name IN $quality_issue_names
            OPTIONAL MATCH (b:Brand)-[:HAS_PRODUCT]->(p)
            RETURN p, b, collect(DISTINCT i.issue_name) AS issue_names,
                   count(DISTINCT f) AS feedback_count
            ORDER BY feedback_count DESC, p.product_name
            """,
            params,
        )
        ctx = empty_context(question, intent)
        for row in rows:
            product = self._node_props(row.get('p'), 'Product')
            brand = self._node_props(row.get('b'), 'Brand')
            if not product:
                continue
            self._add_node(ctx, product)
            if brand:
                self._add_node(ctx, brand)
                self._add_rel(ctx, brand['key'], 'HAS_PRODUCT', product['key'])
            issue_names = list(row.get('issue_names') or [])
            for name in issue_names:
                issue_key = f'IssueName:{name}'
                self._add_node(
                    ctx,
                    {
                        'key': issue_key,
                        'label': 'Issue',
                        'issue_name': name,
                    },
                )
                # Relationship path summarized in facts; concrete ABOUT_ISSUE edges
                # added when feedback nodes are present in other queries.
            ctx['facts'].append(
                {
                    'type': 'product_quality_issues',
                    'product_id': product.get('product_id'),
                    'product_name': product.get('product_name'),
                    'brand': brand.get('brand_name') if brand else None,
                    'issues': issue_names,
                    'feedback_with_issue_count': int(row.get('feedback_count') or 0),
                    'path': 'Product-HAS_FEEDBACK->CustomerFeedback-ABOUT_ISSUE->Issue',
                }
            )
        # Also fetch concrete relationship triples for LLM-ready context
        path_rows = self.store.run_cypher(
            """
            MATCH (p:Product)-[:HAS_FEEDBACK]->(f:CustomerFeedback)-[:ABOUT_ISSUE]->(i:Issue)
            WHERE i.issue_name IN $quality_issue_names
            RETURN p, f, i
            """,
            params,
        )
        for row in path_rows:
            product = self._node_props(row.get('p'), 'Product')
            feedback = self._node_props(row.get('f'), 'CustomerFeedback')
            issue = self._node_props(row.get('i'), 'Issue')
            if product:
                self._add_node(ctx, product)
            if feedback:
                self._add_node(ctx, feedback)
                if product:
                    self._add_rel(ctx, product['key'], 'HAS_FEEDBACK', feedback['key'])
            if issue:
                self._add_node(ctx, issue)
                if feedback:
                    self._add_rel(ctx, feedback['key'], 'ABOUT_ISSUE', issue['key'])
        return ctx

    def _retrieve_products_negative_feedback_returns(
        self, question: str, intent: RetrievalIntent
    ) -> dict[str, Any]:
        sentiment = intent.filters.get('sentiment')
        require_return = intent.filters.get('is_return')

        where_clauses = []
        params: dict[str, Any] = {}
        if sentiment:
            where_clauses.append('f.sentiment = $sentiment')
            params['sentiment'] = sentiment
        if require_return is True:
            where_clauses.append('f.is_return = true')
        elif require_return is False:
            where_clauses.append('f.is_return = false')

        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
        # WHERE must follow the required MATCH on `f` before OPTIONAL MATCH,
        # otherwise Neo4j can fail to apply filters on required variables.
        rows = self.store.run_cypher(
            f"""
            MATCH (p:Product)-[:HAS_FEEDBACK]->(f:CustomerFeedback)
            {where_sql}
            OPTIONAL MATCH (f)-[:ABOUT_ISSUE]->(i:Issue)
            OPTIONAL MATCH (b:Brand)-[:HAS_PRODUCT]->(p)
            RETURN p, b, f, i
            ORDER BY p.product_name, f.feedback_id
            """,
            params,
        )
        ctx = empty_context(question, intent)
        seen_products: set[int] = set()
        for row in rows:
            product = self._node_props(row.get('p'), 'Product')
            brand = self._node_props(row.get('b'), 'Brand')
            feedback = self._node_props(row.get('f'), 'CustomerFeedback')
            issue = self._node_props(row.get('i'), 'Issue')
            if not product or not feedback:
                continue
            self._add_node(ctx, product)
            self._add_node(ctx, feedback)
            self._add_rel(ctx, product['key'], 'HAS_FEEDBACK', feedback['key'])
            if brand:
                self._add_node(ctx, brand)
                self._add_rel(ctx, brand['key'], 'HAS_PRODUCT', product['key'])
            if issue:
                self._add_node(ctx, issue)
                self._add_rel(ctx, feedback['key'], 'ABOUT_ISSUE', issue['key'])
            pid = int(product['product_id'])
            seen_products.add(pid)
            ctx['facts'].append(
                {
                    'type': 'product_feedback_signal',
                    'product_id': pid,
                    'product_name': product.get('product_name'),
                    'brand': brand.get('brand_name') if brand else None,
                    'sentiment': feedback.get('sentiment'),
                    'is_return': bool(feedback.get('is_return')),
                    'return_reason': feedback.get('return_reason'),
                    'issue': issue.get('issue_name') if issue else None,
                    'feedback_text': feedback.get('feedback_text'),
                    'path': 'Product-HAS_FEEDBACK->CustomerFeedback(-ABOUT_ISSUE->Issue)?',
                }
            )
        ctx['facts'].insert(
            0,
            {
                'type': 'result_summary',
                'matching_products': len(seen_products),
                'matching_feedback_rows': len(rows),
                'filters': intent.filters,
            },
        )
        return ctx

    def _retrieve_brands_with_negative_feedback(
        self, question: str, intent: RetrievalIntent
    ) -> dict[str, Any]:
        rows = self.store.run_cypher(
            """
            MATCH (b:Brand)-[:HAS_PRODUCT]->(p:Product)-[:HAS_FEEDBACK]->(f:CustomerFeedback)
            WHERE f.sentiment = 'negative'
            OPTIONAL MATCH (f)-[:ABOUT_ISSUE]->(i:Issue)
            RETURN b, p, f, i
            ORDER BY b.brand_name, p.product_name
            """
        )
        ctx = empty_context(question, intent)
        brand_summary: dict[str, dict[str, Any]] = {}
        for row in rows:
            brand = self._node_props(row.get('b'), 'Brand')
            product = self._node_props(row.get('p'), 'Product')
            feedback = self._node_props(row.get('f'), 'CustomerFeedback')
            issue = self._node_props(row.get('i'), 'Issue')
            if not brand or not product or not feedback:
                continue
            self._add_node(ctx, brand)
            self._add_node(ctx, product)
            self._add_node(ctx, feedback)
            self._add_rel(ctx, brand['key'], 'HAS_PRODUCT', product['key'])
            self._add_rel(ctx, product['key'], 'HAS_FEEDBACK', feedback['key'])
            if issue:
                self._add_node(ctx, issue)
                self._add_rel(ctx, feedback['key'], 'ABOUT_ISSUE', issue['key'])
            bname = brand.get('brand_name') or brand['key']
            bucket = brand_summary.setdefault(
                bname,
                {'brand': bname, 'products': set(), 'negative_feedback_count': 0, 'issues': set()},
            )
            bucket['products'].add(product.get('product_name'))
            bucket['negative_feedback_count'] += 1
            if issue and issue.get('issue_name'):
                bucket['issues'].add(issue['issue_name'])
            ctx['facts'].append(
                {
                    'type': 'brand_negative_feedback',
                    'brand': bname,
                    'product': product.get('product_name'),
                    'product_id': product.get('product_id'),
                    'issue': issue.get('issue_name') if issue else None,
                    'is_return': bool(feedback.get('is_return')),
                    'path': 'Brand-HAS_PRODUCT->Product-HAS_FEEDBACK->CustomerFeedback',
                }
            )
        for bname, bucket in sorted(brand_summary.items()):
            ctx['facts'].insert(
                0,
                {
                    'type': 'brand_negative_summary',
                    'brand': bname,
                    'products': sorted(bucket['products']),
                    'negative_feedback_count': bucket['negative_feedback_count'],
                    'issues': sorted(bucket['issues']),
                },
            )
        return ctx

    def _retrieve_products_high_sales_and_quality_issues(
        self, question: str, intent: RetrievalIntent
    ) -> dict[str, Any]:
        threshold = intent.filters.get('sales_threshold') or 'median_or_above'
        use_highest = threshold == 'highest'

        quality_params = self._quality_issue_params(intent)
        agg_rows = self.store.run_cypher(
            """
            MATCH (p:Product)-[:HAS_FEEDBACK]->(:CustomerFeedback)-[:ABOUT_ISSUE]->(i:Issue)
            WHERE i.issue_name IN $quality_issue_names
            WITH p, collect(DISTINCT i.issue_name) AS issue_names
            MATCH (p)-[:HAS_SALE]->(s:Sale)
            OPTIONAL MATCH (b:Brand)-[:HAS_PRODUCT]->(p)
            WITH p, b, issue_names,
                 sum(s.quantity) AS sales_units,
                 sum(s.total_price) AS sales_revenue
            RETURN p, b, issue_names, sales_units, sales_revenue
            ORDER BY sales_units DESC
            """,
            quality_params,
        )

        ctx = empty_context(question, intent)
        if not agg_rows:
            return ctx

        median: float | None = None
        if not use_highest:
            sales_rows = self.store.run_cypher(
                """
                MATCH (p:Product)-[:HAS_SALE]->(s:Sale)
                RETURN p.product_id AS product_id,
                       sum(s.quantity) AS sales_units
                """
            )
            if not sales_rows:
                return ctx
            units = sorted(int(r['sales_units'] or 0) for r in sales_rows)
            mid = len(units) // 2
            if len(units) % 2 == 1:
                median = float(units[mid])
            else:
                median = float(units[mid - 1] + units[mid]) / 2.0 if units else 0.0
            ctx['facts'].append(
                {
                    'type': 'sales_threshold',
                    'rule': 'median_or_above',
                    'median_sales_units': median,
                }
            )
        else:
            ctx['facts'].append(
                {
                    'type': 'sales_threshold',
                    'rule': 'highest',
                }
            )

        selected_ids: set[int] = set()
        for row in agg_rows:
            sales_units = int(row.get('sales_units') or 0)
            if use_highest:
                # agg_rows already ORDER BY sales_units DESC — keep only the first.
                if selected_ids:
                    break
            elif median is not None and sales_units < median:
                continue
            product = self._node_props(row.get('p'), 'Product')
            brand = self._node_props(row.get('b'), 'Brand')
            if not product:
                continue
            pid = int(product['product_id'])
            selected_ids.add(pid)
            self._add_node(ctx, product)
            if brand:
                self._add_node(ctx, brand)
                self._add_rel(ctx, brand['key'], 'HAS_PRODUCT', product['key'])
            ctx['facts'].append(
                {
                    'type': 'product_high_sales_with_quality_issues',
                    'product_id': pid,
                    'product_name': product.get('product_name'),
                    'brand': brand.get('brand_name') if brand else None,
                    'sales_units': sales_units,
                    'sales_revenue': float(row.get('sales_revenue') or 0),
                    'issues': list(row.get('issue_names') or []),
                    'paths': [
                        'Product-HAS_SALE->Sale',
                        'Product-HAS_FEEDBACK->CustomerFeedback-ABOUT_ISSUE->Issue',
                    ],
                }
            )
            if use_highest:
                break

        if not selected_ids:
            return ctx

        detail_rows = self.store.run_cypher(
            """
            MATCH (p:Product)-[:HAS_FEEDBACK]->(f:CustomerFeedback)-[:ABOUT_ISSUE]->(i:Issue)
            MATCH (p)-[:HAS_SALE]->(s:Sale)
            WHERE p.product_id IN $product_ids
              AND i.issue_name IN $quality_issue_names
            RETURN p, f, i, s
            """,
            {
                'product_ids': list(selected_ids),
                **quality_params,
            },
        )
        for row in detail_rows:
            product = self._node_props(row.get('p'), 'Product')
            sale = self._node_props(row.get('s'), 'Sale')
            feedback = self._node_props(row.get('f'), 'CustomerFeedback')
            issue = self._node_props(row.get('i'), 'Issue')
            if not product:
                continue
            self._add_node(ctx, product)
            if sale:
                self._add_node(ctx, sale)
                self._add_rel(ctx, product['key'], 'HAS_SALE', sale['key'])
            if feedback:
                self._add_node(ctx, feedback)
                self._add_rel(ctx, product['key'], 'HAS_FEEDBACK', feedback['key'])
            if issue:
                self._add_node(ctx, issue)
                if feedback:
                    self._add_rel(ctx, feedback['key'], 'ABOUT_ISSUE', issue['key'])
        return ctx

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def _context_from_product_bundle(
        self, question: str, intent: RetrievalIntent, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        ctx = empty_context(question, intent)
        if not rows:
            return ctx
        row = rows[0]
        product = self._node_props(row.get('p'), 'Product')
        brand = self._node_props(row.get('b'), 'Brand')
        category = self._node_props(row.get('c'), 'Category')
        if not product:
            return ctx
        self._add_node(ctx, product)
        if brand:
            self._add_node(ctx, brand)
            self._add_rel(ctx, brand['key'], 'HAS_PRODUCT', product['key'])
        if category:
            self._add_node(ctx, category)
            self._add_rel(ctx, category['key'], 'HAS_PRODUCT', product['key'])
        sales_units = 0
        for sale_raw in row.get('sales') or []:
            sale = self._node_props(sale_raw, 'Sale')
            if not sale:
                continue
            self._add_node(ctx, sale)
            self._add_rel(ctx, product['key'], 'HAS_SALE', sale['key'])
            sales_units += int(sale.get('quantity') or 0)
        issues = []
        for fb_raw in row.get('feedbacks') or []:
            feedback = self._node_props(fb_raw, 'CustomerFeedback')
            if not feedback:
                continue
            self._add_node(ctx, feedback)
            self._add_rel(ctx, product['key'], 'HAS_FEEDBACK', feedback['key'])
        for issue_raw in row.get('issues') or []:
            issue = self._node_props(issue_raw, 'Issue')
            if not issue:
                continue
            self._add_node(ctx, issue)
            issues.append(issue.get('issue_name'))
        # Link feedback→issue via second query for accuracy
        link_rows = self.store.run_cypher(
            """
            MATCH (p:Product {product_id: $product_id})-[:HAS_FEEDBACK]->(f:CustomerFeedback)
                  -[:ABOUT_ISSUE]->(i:Issue)
            RETURN f.key AS fkey, i.key AS ikey
            """,
            {'product_id': product['product_id']},
        )
        for link in link_rows:
            if link.get('fkey') and link.get('ikey'):
                self._add_rel(ctx, link['fkey'], 'ABOUT_ISSUE', link['ikey'])
        ctx['facts'].append(
            {
                'type': 'product_context',
                'product_id': product.get('product_id'),
                'product_name': product.get('product_name'),
                'brand': brand.get('brand_name') if brand else None,
                'category': category.get('category_name') if category else None,
                'sales_units': sales_units,
                'issues': [i for i in issues if i],
            }
        )
        return ctx

    def _context_from_feedback_rows(
        self, question: str, intent: RetrievalIntent, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        ctx = empty_context(question, intent)
        for row in rows:
            product = self._node_props(row.get('p'), 'Product')
            feedback = self._node_props(row.get('f'), 'CustomerFeedback')
            issue = self._node_props(row.get('i'), 'Issue')
            if product:
                self._add_node(ctx, product)
            if feedback:
                self._add_node(ctx, feedback)
                if product:
                    self._add_rel(ctx, product['key'], 'HAS_FEEDBACK', feedback['key'])
            if issue:
                self._add_node(ctx, issue)
                if feedback:
                    self._add_rel(ctx, feedback['key'], 'ABOUT_ISSUE', issue['key'])
            if product and feedback:
                ctx['facts'].append(
                    {
                        'type': 'feedback_row',
                        'product_id': product.get('product_id'),
                        'product_name': product.get('product_name'),
                        'sentiment': feedback.get('sentiment'),
                        'is_return': bool(feedback.get('is_return')),
                        'return_reason': feedback.get('return_reason'),
                        'issue': issue.get('issue_name') if issue else None,
                        'feedback_text': feedback.get('feedback_text'),
                    }
                )
        return ctx

    @staticmethod
    def _node_props(raw: Any, label: str) -> dict[str, Any] | None:
        if raw is None:
            return None
        if isinstance(raw, dict):
            props = dict(raw)
        else:
            # neo4j.graph.Node behaves like a mapping
            try:
                props = dict(raw)
            except Exception:
                return None
        if not props:
            return None
        key = props.get('key')
        if not key:
            id_map = {
                'Product': 'product_id',
                'Brand': 'brand_id',
                'Category': 'category_id',
                'Sale': 'sale_id',
                'CustomerFeedback': 'feedback_id',
                'Issue': 'issue_id',
            }
            id_prop = id_map.get(label)
            if id_prop and props.get(id_prop) is not None:
                key = f'{label}:{props[id_prop]}'
            else:
                key = f'{label}:unknown'
        out = {'key': key, 'label': label}
        out.update(props)
        out['key'] = key
        out['label'] = label
        return out

    @staticmethod
    def _add_node(ctx: dict[str, Any], node: dict[str, Any]) -> None:
        key = node.get('key')
        if not key:
            return
        existing = {n['key'] for n in ctx['nodes']}
        if key not in existing:
            ctx['nodes'].append(node)

    @staticmethod
    def _add_rel(ctx: dict[str, Any], start: str, rel_type: str, end: str) -> None:
        sig = (start, rel_type, end)
        existing = {(r['start'], r['type'], r['end']) for r in ctx['relationships']}
        if sig not in existing:
            ctx['relationships'].append({'start': start, 'type': rel_type, 'end': end})


def format_retrieval_report(context: dict[str, Any]) -> str:
    """Pretty-print graph context for demos."""
    lines = [
        f"Question:\n{context.get('question')}",
        '',
        'Retrieved entities:',
    ]
    nodes = context.get('nodes') or []
    if not nodes:
        lines.append('  (none)')
    else:
        by_label: dict[str, list[str]] = {}
        for node in nodes:
            label = node.get('label') or 'Unknown'
            name = (
                node.get('product_name')
                or node.get('brand_name')
                or node.get('category_name')
                or node.get('issue_name')
                or node.get('key')
            )
            by_label.setdefault(label, []).append(str(name))
        for label, names in sorted(by_label.items()):
            uniq = sorted(set(names))
            lines.append(f"  {label}: {', '.join(uniq)}")

    lines.append('')
    lines.append('Relationships traversed:')
    intent = context.get('intent') or {}
    rels = intent.get('relationships') or []
    if rels:
        for rel in rels:
            lines.append(f'  {rel}')
    else:
        concrete = context.get('relationships') or []
        if not concrete:
            lines.append('  (none)')
        else:
            types = sorted({r['type'] for r in concrete})
            for t in types:
                lines.append(f'  {t}')

    lines.append('')
    lines.append('Facts:')
    facts = context.get('facts') or []
    if not facts:
        lines.append('  (none)')
    else:
        for fact in facts:
            lines.append(f'  - {fact}')
    return '\n'.join(lines)
