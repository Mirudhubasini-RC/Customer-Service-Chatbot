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

RetailAsk keeps a **business graph** of Brand, Product, Category, Sale, CustomerFeedback, and Issue so owners can inspect relationship-shaped retail facts.

- **Why:** sales ↔ product ↔ feedback ↔ issue paths are awkward as pure SQL narratives but natural as graph traversals.
- **Entities / relationships:** see [`Backend/business_graph/README.md`](Backend/business_graph/README.md).
- **Storage:** in-memory `GraphStore` interface (`InMemoryGraphStore` now; Neo4j-swappable later). No Neo4j required for this step.
- **Build:** from MySQL FKs only (or offline `seed_fixture` matching `seed.sql`).
- **Not in this step:** question → graph retrieval → Qwen answering, agents, or frontend changes.

```bash
cd Backend
source venv/bin/activate
python demo_business_graph.py --seed-only
python -m unittest tests.test_business_graph -v
```

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
