# RetailAsk Business Graph (Step 3B)

This package is the **Business Graph layer**: representation, MySQL→graph sync, and traversal.

- **Persistent store:** Neo4j (`Neo4jGraphStore`)
- **Fallback / unit tests:** in-memory (`InMemoryGraphStore`)
- **Not** Schema RAG, agents, or question→graph→Qwen answering

## Why Neo4j

RetailAsk’s business graph is relationship-shaped (brand → product → sales/feedback → issues). Neo4j gives:

- Persistent, inspectable graph storage (Browser / Cypher)
- Idempotent `MERGE` sync from MySQL
- A production-ready backend for future Graph RAG retrieval

The `GraphStore` interface keeps builder/service independent of Neo4j so tests can stay in-memory.

## Architecture

```
MySQL (system of record)
   ↓
BusinessGraphBuilder
   ↓
Neo4jGraphStore  ──implements──> GraphStore
   ↓
BusinessGraphService (traversals)
   ↓
(future) Graph RAG retrieval
```

In-memory path (tests / offline):

```
seed_fixture / MySQL rows → BusinessGraphBuilder → InMemoryGraphStore → BusinessGraphService
```

## Entities & relationships

```
(:Brand)-[:HAS_PRODUCT]->(:Product)<-[:HAS_PRODUCT]-(:Category)
                              |
                              ├──[:HAS_SALE]->(:Sale)
                              |
                              └──[:HAS_FEEDBACK]->(:CustomerFeedback)
                                                       |
                                                       └──[:ABOUT_ISSUE]->(:Issue)
```

Only FK-backed edges are created (`products.brand_id`, `products.category_id`, `sales.product_id`, `customer_feedback.product_id`, `customer_feedback.issue_id`).

Node identity: MySQL PK property + `key` (`Product:6`). Uniqueness constraints are created on connect.

## Neo4j setup

1. Install Neo4j Desktop or run Docker:

```bash
docker run -d --name retailask-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_neo4j_password \
  neo4j:5
```

2. Copy env vars into `Backend/.env` (see `.env.example`):

| Variable | Example |
|----------|---------|
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | `neo4j` |
| `NEO4J_PASSWORD` | *(your password)* |
| `NEO4J_DATABASE` | `neo4j` |

3. Install dependency: `pip install neo4j` (included in `requirements.txt`).

## Build / sync the graph

```bash
cd Backend
source venv/bin/activate
pip install -r ../requirements.txt

# Sync into Neo4j (MySQL if configured, else seed_fixture)
python demo_business_graph.py --neo4j

# Force seed_fixture → Neo4j (no MySQL)
python demo_business_graph.py --neo4j --seed-only

# Offline in-memory demo (no Neo4j)
python demo_business_graph.py --seed-only
```

Builder uses `clear()` then `MERGE` upserts so identity is stable; running sync twice does not duplicate nodes/relationships.

## Demo Cypher (also printed by `--neo4j`)

```cypher
MATCH (p:Product {product_id: 3})
OPTIONAL MATCH (b:Brand)-[:HAS_PRODUCT]->(p)
OPTIONAL MATCH (c:Category)-[:HAS_PRODUCT]->(p)
OPTIONAL MATCH (p)-[:HAS_FEEDBACK]->(f:CustomerFeedback)
OPTIONAL MATCH (f)-[:ABOUT_ISSUE]->(i:Issue)
RETURN p.product_name, b.brand_name, c.category_name,
       f.sentiment, f.is_return, i.issue_name
```

## Tests

```bash
# Unit tests (InMemoryGraphStore — no Neo4j required)
python -m unittest tests.test_business_graph -v

# Integration tests (requires live Neo4j + env vars; skips if unavailable)
python -m unittest tests.test_business_graph_neo4j -v
```

Expected seed counts: **82 nodes**, **97 relationships**.

## Graph Retrieval (Step 3C)

**Graph Retrieval** turns a retail-owner question into a structured retrieval intent, runs Cypher against Neo4j Aura, and returns a normalized graph context (`nodes`, `relationships`, `facts`).

It is **not** Schema RAG (schema-for-SQL).  
Step 3D adds Qwen answer generation on top of this context (see below).

```
Question → intent parser → Cypher (Neo4j Aura) → graph context
```

```bash
cd Backend
source venv/bin/activate
python demo_graph_retrieval.py
python -m unittest tests.test_graph_retrieval -v
```

## Graph RAG (Step 3D)

Connects Step 3C retrieval to **Qwen2.5-Coder** (`business_graph/graph_answer.py`).

```
Question → GraphRetriever → Neo4j context → Qwen → grounded answer
```

Independent of the main `/query` SQL pipeline. No agents yet.

```bash
python demo_graph_rag.py
python -m unittest tests.test_graph_rag tests.test_graph_retrieval -v
```
