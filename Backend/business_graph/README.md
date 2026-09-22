# RetailAsk Business Graph (Step 3B)

This package is the **Business Graph layer** only: representation, construction from MySQL, and traversal helpers.

It is **not** Schema RAG (DB schema retrieval for SQL).  
It is **not** question → graph retrieval → Qwen answering (future step).  
It is **not** multi-agent orchestration.

## Why RetailAsk needs a business graph

Retail owners ask relationship questions that SQL alone answers awkwardly:

- Which products under a brand have negative feedback and returns?
- What issues sit on high-selling products?
- How do sales and feedback connect for one SKU?

A **business graph** makes Brand / Product / Category / Sale / Feedback / Issue links first-class, while MySQL remains the system of record.

## Entities (nodes)

| Node | MySQL source | Key properties |
|------|----------------|----------------|
| Brand | `brands` | `brand_id`, `brand_name` |
| Category | `categories` | `category_id`, `category_name` |
| Product | `products` | `product_id`, `product_name`, `price`, `brand_id`, `category_id` |
| Sale | `sales` | `sale_id`, `product_id`, `sale_date`, `quantity`, `total_price` |
| CustomerFeedback | `customer_feedback` | `feedback_id`, `product_id`, `issue_id`, `feedback_text`, `sentiment`, `is_return`, `return_reason`, `feedback_date` |
| Issue | `issues` | `issue_id`, `issue_name` |

Node ids are `Label:mysql_id` (e.g. `Product:6`) so every node traces back to MySQL.

## Relationships (edges)

Only FK-backed edges are created:

```
Brand ──HAS_PRODUCT──> Product <──HAS_PRODUCT── Category
                         │
                         ├── HAS_SALE ──> Sale
                         │
                         └── HAS_FEEDBACK ──> CustomerFeedback
                                                   │
                                                   └── ABOUT_ISSUE ──> Issue
```

| Edge | Backed by |
|------|-----------|
| Brand → Product (`HAS_PRODUCT`) | `products.brand_id` |
| Category → Product (`HAS_PRODUCT`) | `products.category_id` |
| Product → Sale (`HAS_SALE`) | `sales.product_id` |
| Product → CustomerFeedback (`HAS_FEEDBACK`) | `customer_feedback.product_id` |
| CustomerFeedback → Issue (`ABOUT_ISSUE`) | `customer_feedback.issue_id` (skipped when NULL) |

No free-text inferred links. `customer_queries` is **not** in this graph.

## How the graph is built

1. `BusinessGraphBuilder.build_from_mysql(...)` reads the six tables, **or**
2. `build_from_records(...)` accepts dict rows (tests / offline demo via `seed_fixture.py`).
3. Nodes are upserted, then relationships are created only when FK values exist.
4. Build logs node counts, relationship counts, and type breakdowns.

## Graph storage abstraction

**Decision:** `InMemoryGraphStore` (pure Python) behind `GraphStore` ABC.

**Why not Neo4j in Step 3B:**
- Project has no Neo4j dependency or deploy config today.
- Seeded graph is small; an in-memory store is enough for construction + inspection.
- Take-home demos should run without a graph database server.

**How to swap later:** implement `GraphStore` with Neo4j (or another backend). Keep using `BusinessGraphBuilder` + `BusinessGraphService` without rewriting callers.

## Traversal helpers

- `get_product(product_id)`
- `get_product_sales(product_id)`
- `get_product_feedback(product_id)`
- `get_product_issues(product_id)`
- `get_products_by_brand(brand_id)`
- `get_products_by_category(category_id)`

## Demo / tests

```bash
cd Backend
source venv/bin/activate
python demo_business_graph.py --seed-only
python -m unittest tests.test_business_graph -v
```
