"""
Deterministic retrieval-intent parsing for Business Graph Retrieval (Step 3C).

Converts a natural-language retail-owner question into a structured intent
(entities, relationships, filters). No LLM call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalIntent:
    """Structured graph retrieval plan derived from a question."""

    intent_type: str
    entities: list[str]
    relationships: list[str]
    filters: dict[str, Any] = field(default_factory=dict)
    product_id: int | None = None
    brand_id: int | None = None
    category_id: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'intent_type': self.intent_type,
            'entities': list(self.entities),
            'relationships': list(self.relationships),
            'filters': dict(self.filters),
            'product_id': self.product_id,
            'brand_id': self.brand_id,
            'category_id': self.category_id,
        }


# Intent type constants
PRODUCTS_WITH_QUALITY_ISSUES = 'products_with_quality_issues'
PRODUCTS_NEGATIVE_FEEDBACK_RETURNS = 'products_negative_feedback_returns'
BRANDS_WITH_NEGATIVE_FEEDBACK = 'brands_with_negative_feedback'
PRODUCTS_HIGH_SALES_AND_QUALITY_ISSUES = 'products_high_sales_and_quality_issues'
PRODUCT_CONTEXT = 'product_context'
PRODUCT_FEEDBACK = 'product_feedback'
PRODUCT_SALES = 'product_sales'
PRODUCT_ISSUES = 'product_issues'
BRAND_PRODUCTS = 'brand_products'
CATEGORY_PRODUCTS = 'category_products'
UNSUPPORTED = 'unsupported'


_QUALITY_RE = re.compile(
    r'\b(quality\s+issues?|issues?|defective|durability|compatibility|'
    r'packaging|battery\s+life|problem|problems)\b',
    re.I,
)
_NEGATIVE_RE = re.compile(r'\b(negative|bad|poor)\b', re.I)
_RETURN_RE = re.compile(r'\b(returns?|returned|refund)\b', re.I)
_FEEDBACK_RE = re.compile(r'\b(feedback|complaints?|reviews?)\b', re.I)
_SALES_RE = re.compile(r'\b(sales?|selling|revenue|units?\s+sold|high\s+sales|good\s+sales|many\s+sales)\b', re.I)
_BRAND_RE = re.compile(r'\bbrands?\b', re.I)
_CATEGORY_RE = re.compile(r'\bcategor(y|ies)\b', re.I)
_PRODUCT_ID_RE = re.compile(r'\bproduct(?:\s*id)?\s*[#:]?\s*(\d+)\b', re.I)
_BRAND_ID_RE = re.compile(r'\bbrand(?:\s*id)?\s*[#:]?\s*(\d+)\b', re.I)
_CATEGORY_ID_RE = re.compile(r'\bcategor(?:y|ies)(?:\s*id)?\s*[#:]?\s*(\d+)\b', re.I)


def parse_retrieval_intent(question: str) -> RetrievalIntent:
    """
    Map a natural-language question to a structured retrieval intent.

    Priority matters: more specific multi-signal patterns first.
    """
    q = (question or '').strip()
    if not q:
        return RetrievalIntent(
            intent_type=UNSUPPORTED,
            entities=[],
            relationships=[],
            filters={'reason': 'empty_question'},
        )

    lower = q.lower()
    product_id = _match_int(_PRODUCT_ID_RE, q)
    brand_id = _match_int(_BRAND_ID_RE, q)
    category_id = _match_int(_CATEGORY_ID_RE, q)

    has_quality = bool(_QUALITY_RE.search(q))
    has_negative = bool(_NEGATIVE_RE.search(q))
    has_return = bool(_RETURN_RE.search(q))
    has_feedback = bool(_FEEDBACK_RE.search(q))
    has_sales = bool(_SALES_RE.search(q))
    has_brand = bool(_BRAND_RE.search(q))
    has_category = bool(_CATEGORY_RE.search(q))

    # Explicit id-scoped lookups
    if product_id is not None:
        if has_sales and not (has_feedback or has_quality or has_return):
            return RetrievalIntent(
                intent_type=PRODUCT_SALES,
                entities=['Product', 'Sale'],
                relationships=['Product-HAS_SALE->Sale'],
                product_id=product_id,
            )
        if has_quality or (has_feedback and 'issue' in lower):
            return RetrievalIntent(
                intent_type=PRODUCT_ISSUES,
                entities=['Product', 'CustomerFeedback', 'Issue'],
                relationships=[
                    'Product-HAS_FEEDBACK->CustomerFeedback',
                    'CustomerFeedback-ABOUT_ISSUE->Issue',
                ],
                product_id=product_id,
            )
        if has_feedback or has_negative or has_return:
            return RetrievalIntent(
                intent_type=PRODUCT_FEEDBACK,
                entities=['Product', 'CustomerFeedback', 'Issue'],
                relationships=[
                    'Product-HAS_FEEDBACK->CustomerFeedback',
                    'CustomerFeedback-ABOUT_ISSUE->Issue',
                ],
                filters={
                    'sentiment': 'negative' if has_negative else None,
                    'is_return': True if has_return else None,
                },
                product_id=product_id,
            )
        return RetrievalIntent(
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
        )

    if brand_id is not None:
        return RetrievalIntent(
            intent_type=BRAND_PRODUCTS,
            entities=['Brand', 'Product'],
            relationships=['Brand-HAS_PRODUCT->Product'],
            brand_id=brand_id,
        )

    if category_id is not None:
        return RetrievalIntent(
            intent_type=CATEGORY_PRODUCTS,
            entities=['Category', 'Product'],
            relationships=['Category-HAS_PRODUCT->Product'],
            category_id=category_id,
        )

    # High sales + quality issues
    if has_sales and has_quality:
        return RetrievalIntent(
            intent_type=PRODUCTS_HIGH_SALES_AND_QUALITY_ISSUES,
            entities=['Product', 'Sale', 'CustomerFeedback', 'Issue'],
            relationships=[
                'Product-HAS_SALE->Sale',
                'Product-HAS_FEEDBACK->CustomerFeedback',
                'CustomerFeedback-ABOUT_ISSUE->Issue',
            ],
            filters={
                'require_issue': True,
                'sales_threshold': 'median_or_above',
            },
        )

    # Brands with negative feedback
    if has_brand and (has_negative or has_feedback):
        return RetrievalIntent(
            intent_type=BRANDS_WITH_NEGATIVE_FEEDBACK,
            entities=['Brand', 'Product', 'CustomerFeedback'],
            relationships=[
                'Brand-HAS_PRODUCT->Product',
                'Product-HAS_FEEDBACK->CustomerFeedback',
            ],
            filters={'sentiment': 'negative'},
        )

    # Negative feedback + returns
    if (has_negative and has_feedback and has_return) or (
        has_negative and has_return
    ) or (has_feedback and has_return and has_negative):
        return RetrievalIntent(
            intent_type=PRODUCTS_NEGATIVE_FEEDBACK_RETURNS,
            entities=['Product', 'CustomerFeedback', 'Issue'],
            relationships=[
                'Product-HAS_FEEDBACK->CustomerFeedback',
                'CustomerFeedback-ABOUT_ISSUE->Issue',
            ],
            filters={'sentiment': 'negative', 'is_return': True},
        )

    if has_return and (has_feedback or has_negative or has_quality):
        return RetrievalIntent(
            intent_type=PRODUCTS_NEGATIVE_FEEDBACK_RETURNS,
            entities=['Product', 'CustomerFeedback', 'Issue'],
            relationships=[
                'Product-HAS_FEEDBACK->CustomerFeedback',
                'CustomerFeedback-ABOUT_ISSUE->Issue',
            ],
            filters={
                'sentiment': 'negative' if has_negative else None,
                'is_return': True,
            },
        )

    # Quality issues (default for issue-oriented questions)
    if has_quality:
        return RetrievalIntent(
            intent_type=PRODUCTS_WITH_QUALITY_ISSUES,
            entities=['Product', 'CustomerFeedback', 'Issue'],
            relationships=[
                'Product-HAS_FEEDBACK->CustomerFeedback',
                'CustomerFeedback-ABOUT_ISSUE->Issue',
            ],
            filters={'require_issue': True},
        )

    if has_negative and has_feedback:
        return RetrievalIntent(
            intent_type=PRODUCTS_NEGATIVE_FEEDBACK_RETURNS,
            entities=['Product', 'CustomerFeedback', 'Issue'],
            relationships=[
                'Product-HAS_FEEDBACK->CustomerFeedback',
                'CustomerFeedback-ABOUT_ISSUE->Issue',
            ],
            filters={'sentiment': 'negative', 'is_return': None},
        )

    if has_brand and has_category:
        return RetrievalIntent(
            intent_type=UNSUPPORTED,
            entities=['Brand', 'Category'],
            relationships=[],
            filters={'reason': 'ambiguous_brand_category'},
        )

    return RetrievalIntent(
        intent_type=UNSUPPORTED,
        entities=[],
        relationships=[],
        filters={'reason': 'no_matching_graph_pattern'},
    )


def _match_int(pattern: re.Pattern[str], text: str) -> int | None:
    m = pattern.search(text)
    if not m:
        return None
    return int(m.group(1))
