# RetailAsk — Retail Owner Analytics Chatbot

AI retail analytics assistant: React frontend + Flask backend + MySQL + Hugging Face Qwen (NL→SQL) with **Schema RAG**.

RetailAsk is built for **retail owners / business analytics**, not end-customer support.

## Schema RAG (Step 2)

**Schema RAG** retrieves only the database schema tables needed to answer a question, instead of stuffing the entire schema into every LLM prompt.

### Why RetailAsk uses it
- The schema is growing (products, sales, brands, categories, issues, customer_feedback, customer_queries).
- Sending every table on every question wastes context and confuses SQL generation.
- Semantic retrieval keeps Qwen focused on the relevant tables and relationships.

### How retrieval works
1. Each table is documented in `Backend/schema_kb/schema_docs.json` (purpose, columns, FKs, example questions).
2. Documents are embedded locally with `sentence-transformers` (`all-MiniLM-L6-v2` by default).
3. The user question is embedded and ranked by **cosine similarity** (not keyword matching).
4. Top matching tables are expanded by **foreign-key neighbors** (e.g. `sales` also pulls `products`).
5. A concise schema context is built and passed to **Qwen2.5-Coder** for SQL generation.

> Schema RAG is **only** for database-schema retrieval for NL→SQL.  
> It is **not** Business Graph RAG. The business graph layer lives in `Backend/business_graph/` (Step 3B).

### Pipeline
```
User question
  → Schema RAG (semantic retrieve + FK expand)
  → Qwen2.5-Coder (SQL)
  → MySQL
  → Qwen (natural-language explanation)
```

### Demo Schema RAG locally
```bash
cd Backend
source venv/bin/activate
pip install -r ../requirements.txt
python demo_schema_rag.py
# optional: also call Qwen for SQL
python demo_schema_rag.py --with-sql
```

## Business Graph (Step 3B)

RetailAsk keeps a **business graph** of Brand, Product, Category, Sale, CustomerFeedback, and Issue.

- **Persistent storage:** Neo4j via `Neo4jGraphStore` (implements `GraphStore`)
- **Fallback / unit tests:** `InMemoryGraphStore`
- **Sync:** MySQL → `BusinessGraphBuilder` → Neo4j (`MERGE`, uniqueness constraints)
- **Not in this step:** question → graph retrieval → Qwen, agents, or frontend changes

Docs: [`Backend/business_graph/README.md`](Backend/business_graph/README.md)

```bash
cd Backend
source venv/bin/activate
pip install -r ../requirements.txt

# Neo4j sync + traversal demo
python demo_business_graph.py --neo4j

# Offline in-memory demo
python demo_business_graph.py --seed-only

# Unit tests (no Neo4j)
python -m unittest tests.test_business_graph -v

# Neo4j integration tests (skips if Neo4j env missing)
python -m unittest tests.test_business_graph_neo4j -v
```

Env: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` (see `Backend/.env.example`).

## Graph Retrieval (Step 3C)

Retrieves relationship-shaped facts from Neo4j (intent → Cypher → context). Does **not** call Qwen yet.

```bash
cd Backend
source venv/bin/activate
python demo_graph_retrieval.py
python -m unittest tests.test_graph_retrieval -v
```

### Graph RAG (Step 3D)
```bash
python demo_graph_rag.py
python -m unittest tests.test_graph_rag tests.test_graph_retrieval -v
```

See [`Backend/business_graph/README.md`](Backend/business_graph/README.md).

## Deploy on Render (recommended)

You need **3 things**:

1. **Backend** — Render Web Service (Flask)
2. **Frontend** — Render Static Site (React)
3. **MySQL** — external (Render has no MySQL; use [Aiven](https://aiven.io) free MySQL)

### Option A — Blueprint

1. Push this repo to GitHub.
2. In Render: **New → Blueprint** → select the repo.
3. Fill in the prompted env vars.
4. After backend is live, set frontend `REACT_APP_API_URL` to `https://<your-backend>.onrender.com` and redeploy frontend.
5. Set backend `FRONTEND_URL` to `https://<your-frontend>.onrender.com`.

### Option B — Manual services

#### Backend Web Service

- **Root Directory:** `Backend`
- **Build Command:** `pip install -r ../requirements.txt`
- **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`

| Key | Example |
|-----|---------|
| `HUGGINGFACE_API_KEY` | your HF token |
| `HF_MODEL` | `Qwen/Qwen2.5-Coder-7B-Instruct:cheapest` |
| `DB_HOST` | Aiven host |
| `DB_PORT` | Aiven port |
| `DB_USER` | `avnadmin` |
| `DB_PASSWORD` | Aiven password |
| `DB_NAME` | `defaultdb` |
| `DB_SSL` | `required` |
| `FRONTEND_URL` | frontend Render URL |

#### Frontend Static Site

- **Root Directory:** `Frontend/my-chat-bot`
- **Build Command:** `npm install && npm run build`
- **Publish Directory:** `build`
- Env: `REACT_APP_API_URL` = backend Render URL

### MySQL setup

Import `Backend/seed.sql` into Aiven `defaultdb`, then set the DB env vars above.

For an existing database that already has the old 3 tables, apply:
`Backend/migrations/001_retailask_2_data_model.sql`

## Local development

```bash
# Backend
cd Backend
python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
cp .env.example .env   # fill in values
python app.py

# Frontend (new terminal)
cd Frontend/my-chat-bot
npm install
npm start
```

Frontend defaults to `http://localhost:8000` when `REACT_APP_API_URL` is unset.

First Schema RAG request (or `demo_schema_rag.py`) downloads the local embedding model and caches table embeddings under `Backend/schema_kb/schema_embeddings.npz`.
