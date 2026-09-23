# Graph Retrieval (Step 3C)

## What it does

Given a natural-language **retail-owner** question, Graph Retrieval:

1. Parses a **structured retrieval intent** (entities, relationships, filters) — deterministic, no LLM
2. Runs **Cypher** against Neo4j Aura via `Neo4jGraphStore`
3. Returns a normalized **graph context** for a later Qwen step:

```json
{
  "question": "...",
  "intent": { "intent_type": "...", "entities": [], "relationships": [], "filters": {} },
  "nodes": [],
  "relationships": [],
  "facts": [],
  "source": "neo4j"
}
```

This step **stops at context**. It does not generate a final answer.

## How Cypher is used

`GraphRetriever` issues relationship-aware queries such as:

- `(:Product)-[:HAS_FEEDBACK]->(:CustomerFeedback)-[:ABOUT_ISSUE]->(:Issue)` for quality issues
- filters on `sentiment` / `is_return` for negative feedback + returns
- `(:Brand)-[:HAS_PRODUCT]->(:Product)-[:HAS_FEEDBACK]->(:CustomerFeedback)` for brand-level negatives
- sales aggregation + issue paths for “high sales and quality issues” (median sales threshold)

Structured helpers also exist: `retrieve_product_context`, `retrieve_product_feedback`, `retrieve_product_sales`, `retrieve_product_issues`, `retrieve_brand_products`, `retrieve_category_products`.

## Why this is different from Schema RAG

| | Schema RAG | Graph Retrieval |
|--|------------|-----------------|
| Source | MySQL **schema docs** embeddings | Neo4j **business graph** |
| Purpose | Choose tables for SQL generation | Fetch relationship facts |
| Output | Schema context for Qwen→SQL | Graph context (nodes/rels/facts) |
| Next | Qwen SQL | (future) Qwen answer from graph |

## Demo / tests

```bash
python demo_graph_retrieval.py
python -m unittest tests.test_graph_retrieval -v
```
