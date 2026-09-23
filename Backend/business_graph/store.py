"""
Graph storage abstraction for RetailAsk Business Graph.

Primary persistent store: Neo4jGraphStore (see neo4j_store.py)
Lightweight fallback / unit tests: InMemoryGraphStore (this file)

Both implement GraphStore so BusinessGraphBuilder / BusinessGraphService
stay storage-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Iterable

from .models import GraphNode, GraphRelationship, NodeLabel, RelType, node_key


class GraphStore(ABC):
    """Storage-agnostic graph API (Neo4j in production, in-memory for tests)."""

    @abstractmethod
    def clear(self) -> None:
        ...

    @abstractmethod
    def upsert_node(self, node: GraphNode) -> None:
        ...

    @abstractmethod
    def upsert_relationship(self, rel: GraphRelationship) -> None:
        ...

    @abstractmethod
    def get_node(self, key: str) -> GraphNode | None:
        ...

    @abstractmethod
    def get_nodes_by_label(self, label: NodeLabel) -> list[GraphNode]:
        ...

    @abstractmethod
    def get_neighbors(
        self,
        key: str,
        rel_type: RelType | None = None,
        direction: str = 'out',
    ) -> list[tuple[GraphRelationship, GraphNode]]:
        """
        direction: 'out' | 'in' | 'both'
        Returns list of (relationship, neighbor_node).
        """

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        ...


class InMemoryGraphStore(GraphStore):
    """
    Simple directed multigraph stored in process memory.

    Kept for unit tests and offline demos when Neo4j is unavailable.
    Nodes keyed by `Label:mysql_id`. Relationships stored as adjacency lists.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._out: dict[str, list[GraphRelationship]] = defaultdict(list)
        self._in: dict[str, list[GraphRelationship]] = defaultdict(list)
        self._rel_index: set[tuple[str, str, str]] = set()

    def clear(self) -> None:
        self._nodes.clear()
        self._out.clear()
        self._in.clear()
        self._rel_index.clear()

    def upsert_node(self, node: GraphNode) -> None:
        self._nodes[node.key] = GraphNode(
            key=node.key,
            label=node.label,
            properties=dict(node.properties),
        )

    def upsert_relationship(self, rel: GraphRelationship) -> None:
        if rel.start_key not in self._nodes or rel.end_key not in self._nodes:
            raise KeyError(
                f'Cannot create {rel.rel_type.value}: missing node '
                f'{rel.start_key!r} or {rel.end_key!r}'
            )
        sig = (rel.start_key, rel.rel_type.value, rel.end_key)
        if sig in self._rel_index:
            return
        stored = GraphRelationship(
            start_key=rel.start_key,
            rel_type=rel.rel_type,
            end_key=rel.end_key,
            properties=dict(rel.properties),
        )
        self._out[rel.start_key].append(stored)
        self._in[rel.end_key].append(stored)
        self._rel_index.add(sig)

    def get_node(self, key: str) -> GraphNode | None:
        node = self._nodes.get(key)
        if node is None:
            return None
        return GraphNode(key=node.key, label=node.label, properties=dict(node.properties))

    def get_nodes_by_label(self, label: NodeLabel) -> list[GraphNode]:
        return [
            GraphNode(key=n.key, label=n.label, properties=dict(n.properties))
            for n in self._nodes.values()
            if n.label == label
        ]

    def get_neighbors(
        self,
        key: str,
        rel_type: RelType | None = None,
        direction: str = 'out',
    ) -> list[tuple[GraphRelationship, GraphNode]]:
        if direction not in ('out', 'in', 'both'):
            raise ValueError("direction must be 'out', 'in', or 'both'")

        rels: list[GraphRelationship] = []
        if direction in ('out', 'both'):
            rels.extend(self._out.get(key, []))
        if direction in ('in', 'both'):
            rels.extend(self._in.get(key, []))

        results: list[tuple[GraphRelationship, GraphNode]] = []
        for rel in rels:
            if rel_type is not None and rel.rel_type != rel_type:
                continue
            neighbor_key = rel.end_key if rel.start_key == key else rel.start_key
            neighbor = self._nodes.get(neighbor_key)
            if neighbor is None:
                continue
            results.append(
                (
                    GraphRelationship(
                        start_key=rel.start_key,
                        rel_type=rel.rel_type,
                        end_key=rel.end_key,
                        properties=dict(rel.properties),
                    ),
                    GraphNode(
                        key=neighbor.key,
                        label=neighbor.label,
                        properties=dict(neighbor.properties),
                    ),
                )
            )
        return results

    def stats(self) -> dict[str, Any]:
        by_label: dict[str, int] = defaultdict(int)
        for node in self._nodes.values():
            by_label[node.label.value] += 1
        by_rel: dict[str, int] = defaultdict(int)
        for rels in self._out.values():
            for rel in rels:
                by_rel[rel.rel_type.value] += 1
        return {
            'node_count': len(self._nodes),
            'relationship_count': len(self._rel_index),
            'node_types': dict(sorted(by_label.items())),
            'relationship_types': dict(sorted(by_rel.items())),
            'storage': 'InMemoryGraphStore',
        }

    def make_key(self, label: NodeLabel, record_id: int) -> str:
        return node_key(label, record_id)

    def iter_relationships(self) -> Iterable[GraphRelationship]:
        for rels in self._out.values():
            for rel in rels:
                yield rel
