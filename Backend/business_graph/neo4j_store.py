"""
Neo4j-backed GraphStore for RetailAsk Business Graph.

Primary persistent storage for Step 3B revision.
InMemoryGraphStore remains available for unit tests / offline fallback.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .models import (
    ID_PROPERTY,
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelType,
    node_key,
    parse_node_key,
)
from .store import GraphStore

logger = logging.getLogger('retail-agent')

# All RetailAsk business-graph labels (used for clear / constraints).
RETAIL_LABELS: tuple[NodeLabel, ...] = tuple(NodeLabel)


def neo4j_config_from_env() -> dict[str, str]:
    """Load Neo4j connection settings from environment (no hardcoded secrets)."""
    uri = (os.getenv('NEO4J_URI') or '').strip()
    username = (os.getenv('NEO4J_USERNAME') or os.getenv('NEO4J_USER') or '').strip()
    password = os.getenv('NEO4J_PASSWORD') or ''
    database = (os.getenv('NEO4J_DATABASE') or 'neo4j').strip() or 'neo4j'
    if not uri:
        raise RuntimeError('NEO4J_URI is not configured')
    if not username:
        raise RuntimeError('NEO4J_USERNAME is not configured')
    if password == '' and os.getenv('NEO4J_ALLOW_EMPTY_PASSWORD', '').lower() not in (
        '1',
        'true',
        'yes',
    ):
        # Allow empty only if explicitly opted in (rare local setups).
        raise RuntimeError('NEO4J_PASSWORD is not configured')
    return {
        'uri': uri,
        'username': username,
        'password': password,
        'database': database,
    }


class Neo4jGraphStore(GraphStore):
    """
    Persistent graph store using the official Neo4j Python driver.

    Nodes carry:
      - key: stable `Label:mysql_id` string
      - <id_property>: MySQL primary key (unique constraint per label)
      - remaining business properties from MySQL
    """

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
        driver: Any | None = None,
        ensure_schema: bool = True,
    ):
        if driver is not None:
            self._driver = driver
            self._database = database or os.getenv('NEO4J_DATABASE') or 'neo4j'
            self._owns_driver = False
        else:
            cfg = {
                'uri': uri,
                'username': username,
                'password': password,
                'database': database,
            }
            if not cfg['uri'] or not cfg['username'] or cfg['password'] is None:
                env = neo4j_config_from_env()
                cfg = {k: cfg[k] if cfg[k] is not None else env[k] for k in env}
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                cfg['uri'],
                auth=(cfg['username'], cfg['password']),
            )
            self._database = cfg['database']
            self._owns_driver = True

        self._driver.verify_connectivity()
        if ensure_schema:
            self.ensure_constraints()
        logger.info(
            'Neo4jGraphStore connected | database=%s',
            self._database,
        )

    @classmethod
    def from_env(cls, ensure_schema: bool = True) -> 'Neo4jGraphStore':
        cfg = neo4j_config_from_env()
        return cls(
            uri=cfg['uri'],
            username=cfg['username'],
            password=cfg['password'],
            database=cfg['database'],
            ensure_schema=ensure_schema,
        )

    def close(self) -> None:
        if self._owns_driver and self._driver is not None:
            self._driver.close()

    def __enter__(self) -> 'Neo4jGraphStore':
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _session(self):
        return self._driver.session(database=self._database)

    def ensure_constraints(self) -> None:
        """Create uniqueness constraints on MySQL PK and graph key per label."""
        statements = []
        for label in RETAIL_LABELS:
            id_prop = ID_PROPERTY[label]
            label_name = label.value
            statements.append(
                f'CREATE CONSTRAINT retailask_{label_name.lower()}_{id_prop} IF NOT EXISTS '
                f'FOR (n:{label_name}) REQUIRE n.{id_prop} IS UNIQUE'
            )
            statements.append(
                f'CREATE CONSTRAINT retailask_{label_name.lower()}_key IF NOT EXISTS '
                f'FOR (n:{label_name}) REQUIRE n.key IS UNIQUE'
            )
        with self._session() as session:
            for cypher in statements:
                session.run(cypher)
        logger.info('Neo4j uniqueness constraints ensured | labels=%s', len(RETAIL_LABELS))

    def clear(self) -> None:
        """Remove all RetailAsk business-graph nodes (and their relationships)."""
        labels = '|'.join(label.value for label in RETAIL_LABELS)
        cypher = f'MATCH (n:{labels}) DETACH DELETE n'
        with self._session() as session:
            session.run(cypher)
        logger.info('Neo4j RetailAsk nodes cleared | labels=%s', labels)

    def upsert_node(self, node: GraphNode) -> None:
        id_prop = ID_PROPERTY[node.label]
        record_id = node.properties.get(id_prop)
        if record_id is None:
            raise ValueError(f'Node {node.key} missing identity property {id_prop}')

        props = dict(node.properties)
        props['key'] = node.key
        props[id_prop] = int(record_id)

        # MERGE on MySQL PK; SET all properties (idempotent).
        cypher = (
            f'MERGE (n:{node.label.value} {{{id_prop}: $record_id}}) '
            f'SET n += $props'
        )
        with self._session() as session:
            session.run(cypher, record_id=int(record_id), props=props)

    def upsert_relationship(self, rel: GraphRelationship) -> None:
        start_label, start_id = parse_node_key(rel.start_key)
        end_label, end_id = parse_node_key(rel.end_key)
        start_id_prop = ID_PROPERTY[start_label]
        end_id_prop = ID_PROPERTY[end_label]
        rel_type = rel.rel_type.value
        props = dict(rel.properties)

        cypher = (
            f'MATCH (a:{start_label.value} {{{start_id_prop}: $start_id}}) '
            f'MATCH (b:{end_label.value} {{{end_id_prop}: $end_id}}) '
            f'MERGE (a)-[r:{rel_type}]->(b) '
            f'SET r += $props '
            f'RETURN a.key AS start_key, b.key AS end_key'
        )
        with self._session() as session:
            record = session.run(
                cypher,
                start_id=start_id,
                end_id=end_id,
                props=props,
            ).single()
            if record is None:
                raise KeyError(
                    f'Cannot create {rel_type}: missing node '
                    f'{rel.start_key!r} or {rel.end_key!r}'
                )

    def get_node(self, key: str) -> GraphNode | None:
        label, _record_id = parse_node_key(key)
        cypher = f'MATCH (n:{label.value} {{key: $key}}) RETURN n'
        with self._session() as session:
            record = session.run(cypher, key=key).single()
            if record is None:
                return None
            return self._node_from_neo4j(label, record['n'])

    def get_nodes_by_label(self, label: NodeLabel) -> list[GraphNode]:
        cypher = f'MATCH (n:{label.value}) RETURN n ORDER BY n.key'
        with self._session() as session:
            return [
                self._node_from_neo4j(label, record['n'])
                for record in session.run(cypher)
            ]

    def get_neighbors(
        self,
        key: str,
        rel_type: RelType | None = None,
        direction: str = 'out',
    ) -> list[tuple[GraphRelationship, GraphNode]]:
        if direction not in ('out', 'in', 'both'):
            raise ValueError("direction must be 'out', 'in', or 'both'")

        label, _ = parse_node_key(key)
        rel_filter = f':{rel_type.value}' if rel_type is not None else ''

        queries = []
        if direction in ('out', 'both'):
            queries.append(
                (
                    'out',
                    f'MATCH (n:{label.value} {{key: $key}})-[r{rel_filter}]->(m) '
                    f'RETURN type(r) AS rel_type, properties(r) AS rel_props, '
                    f'labels(m) AS labels, properties(m) AS props, m.key AS neighbor_key',
                )
            )
        if direction in ('in', 'both'):
            queries.append(
                (
                    'in',
                    f'MATCH (n:{label.value} {{key: $key}})<-[r{rel_filter}]-(m) '
                    f'RETURN type(r) AS rel_type, properties(r) AS rel_props, '
                    f'labels(m) AS labels, properties(m) AS props, m.key AS neighbor_key',
                )
            )

        results: list[tuple[GraphRelationship, GraphNode]] = []
        with self._session() as session:
            for direction_name, cypher in queries:
                for record in session.run(cypher, key=key):
                    neighbor_label = self._pick_label(record['labels'])
                    neighbor = GraphNode(
                        key=record['neighbor_key']
                        or node_key(
                            neighbor_label,
                            int(record['props'][ID_PROPERTY[neighbor_label]]),
                        ),
                        label=neighbor_label,
                        properties=self._clean_props(record['props']),
                    )
                    rel_type_enum = RelType(record['rel_type'])
                    if direction_name == 'out':
                        start_key, end_key = key, neighbor.key
                    else:
                        start_key, end_key = neighbor.key, key
                    results.append(
                        (
                            GraphRelationship(
                                start_key=start_key,
                                rel_type=rel_type_enum,
                                end_key=end_key,
                                properties=dict(record['rel_props'] or {}),
                            ),
                            neighbor,
                        )
                    )
        return results

    def stats(self) -> dict[str, Any]:
        with self._session() as session:
            by_label: dict[str, int] = {}
            total_nodes = 0
            for label in RETAIL_LABELS:
                count = session.run(
                    f'MATCH (n:{label.value}) RETURN count(n) AS c'
                ).single()['c']
                by_label[label.value] = int(count)
                total_nodes += int(count)

            by_rel: dict[str, int] = {}
            total_rels = 0
            for rel in RelType:
                count = session.run(
                    f'MATCH ()-[r:{rel.value}]->() RETURN count(r) AS c'
                ).single()['c']
                by_rel[rel.value] = int(count)
                total_rels += int(count)

        return {
            'node_count': total_nodes,
            'relationship_count': total_rels,
            'node_types': dict(sorted(by_label.items())),
            'relationship_types': dict(sorted(by_rel.items())),
            'storage': 'Neo4jGraphStore',
            'database': self._database,
        }

    def run_cypher(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Escape hatch for demos / inspection (not used by GraphStore service)."""
        with self._session() as session:
            return [dict(record) for record in session.run(cypher, parameters or {})]

    @staticmethod
    def _pick_label(labels: list[str]) -> NodeLabel:
        for label in RETAIL_LABELS:
            if label.value in labels:
                return label
        raise ValueError(f'No RetailAsk label in {labels}')

    @staticmethod
    def _clean_props(props: dict[str, Any] | None) -> dict[str, Any]:
        cleaned = dict(props or {})
        # Keep key in properties for traceability; service mostly uses business fields.
        return cleaned

    @classmethod
    def _node_from_neo4j(cls, label: NodeLabel, neo_node: Any) -> GraphNode:
        props = dict(neo_node)
        key = props.get('key') or node_key(label, int(props[ID_PROPERTY[label]]))
        return GraphNode(key=key, label=label, properties=cls._clean_props(props))
