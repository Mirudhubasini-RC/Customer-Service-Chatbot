# RetailAsk — Customer Service Chatbot

AI customer support chatbot for retail: React frontend + Flask backend + MySQL + Hugging Face (NL→SQL).

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
