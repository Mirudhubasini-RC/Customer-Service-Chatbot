"""Node labels and relationship types for the RetailAsk business graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeLabel(str, Enum):
    BRAND = 'Brand'
    PRODUCT = 'Product'
    CATEGORY = 'Category'
    SALE = 'Sale'
    CUSTOMER_FEEDBACK = 'CustomerFeedback'
    ISSUE = 'Issue'


class RelType(str, Enum):
    HAS_PRODUCT = 'HAS_PRODUCT'  # Brand|Category → Product
    HAS_SALE = 'HAS_SALE'  # Product → Sale
    HAS_FEEDBACK = 'HAS_FEEDBACK'  # Product → CustomerFeedback
    ABOUT_ISSUE = 'ABOUT_ISSUE'  # CustomerFeedback → Issue


def node_key(label: NodeLabel | str, record_id: int) -> str:
    """Stable graph node id that preserves the MySQL primary key."""
    label_value = label.value if isinstance(label, NodeLabel) else str(label)
    return f'{label_value}:{int(record_id)}'


# MySQL primary-key property used for Neo4j uniqueness / MERGE
ID_PROPERTY: dict[NodeLabel, str] = {
    NodeLabel.BRAND: 'brand_id',
    NodeLabel.PRODUCT: 'product_id',
    NodeLabel.CATEGORY: 'category_id',
    NodeLabel.SALE: 'sale_id',
    NodeLabel.CUSTOMER_FEEDBACK: 'feedback_id',
    NodeLabel.ISSUE: 'issue_id',
}


def parse_node_key(key: str) -> tuple[NodeLabel, int]:
    """Parse `Product:6` → (NodeLabel.PRODUCT, 6)."""
    if ':' not in key:
        raise ValueError(f'Invalid node key: {key!r}')
    label_str, id_str = key.split(':', 1)
    return NodeLabel(label_str), int(id_str)


@dataclass
class GraphNode:
    key: str
    label: NodeLabel
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def record_id(self) -> int | None:
        """Underlying MySQL primary key when present."""
        for candidate in (
            'product_id',
            'brand_id',
            'category_id',
            'sale_id',
            'feedback_id',
            'issue_id',
        ):
            if candidate in self.properties and self.properties[candidate] is not None:
                return int(self.properties[candidate])
        return None


@dataclass
class GraphRelationship:
    start_key: str
    rel_type: RelType
    end_key: str
    properties: dict[str, Any] = field(default_factory=dict)
