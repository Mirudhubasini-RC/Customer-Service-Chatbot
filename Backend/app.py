from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import os
import re
import json
import logging
import requests
from decimal import Decimal
from datetime import date, datetime
from dotenv import load_dotenv

from schema_rag import get_schema_rag

load_dotenv(override=True)

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'agent.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('retail-agent')

api_key = os.getenv('HUGGINGFACE_API_KEY')
# LLM provider: huggingface (default) | groq (free tier) | ollama (free local)
LLM_PROVIDER = (os.getenv('LLM_PROVIDER') or 'huggingface').strip().lower()
API_URL = os.getenv(
    'HF_API_URL',
    'https://router.huggingface.co/v1/chat/completions',
)
MODEL = os.getenv('HF_MODEL', 'Qwen/Qwen2.5-Coder-7B-Instruct:cheapest')

GROQ_API_URL = os.getenv(
    'GROQ_API_URL',
    'https://api.groq.com/openai/v1/chat/completions',
)
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')

OLLAMA_API_URL = os.getenv(
    'OLLAMA_API_URL',
    'http://127.0.0.1:11434/v1/chat/completions',
)
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b')

app = Flask(__name__)

frontend_origin = os.getenv('FRONTEND_URL', '*').strip() or '*'
# Browsers reject Access-Control-Allow-Origin: * when credentials are enabled.
cors_credentials = frontend_origin != '*'
CORS(
    app,
    resources={r"/*": {"origins": frontend_origin}},
    supports_credentials=cors_credentials,
)

db_config = {
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'database': os.getenv('DB_NAME', 'salesdb'),
    'port': int(os.getenv('DB_PORT', '3306')),
}

# Aiven and most cloud MySQL require SSL
if os.getenv('DB_SSL', '').lower() in ('1', 'true', 'required', 'yes'):
    db_config['ssl_disabled'] = False
    db_config['ssl_verify_cert'] = False
    db_config['ssl_verify_identity'] = False
    ssl_ca = os.getenv('DB_SSL_CA')
    if ssl_ca:
        db_config['ssl_ca'] = ssl_ca

# Schema for NL→SQL is retrieved via Schema RAG (see schema_rag.py + schema_kb/).
# Do not paste the full database schema into every prompt.

CHAT_SYSTEM_PROMPT = (
    'You are a friendly retail customer support assistant for RetailAsk. '
    'Answer clearly in 2-4 short sentences. '
    'Help with products, sales, recommendations, and support. '
    'Do not invent exact database numbers.'
)

SQL_GENERATION_SYSTEM_PROMPT = (
    'You convert retail analytics questions into a single MySQL SELECT query. '
    'Use ONLY the retrieved schema context from Schema RAG. Its Notes are authoritative for '
    'business semantics: high vs highest sales, quality-issue allowlist/exclusions, '
    'SUM(sales.quantity) definitions, and the customer_feedback→issues quality path. '
    'Do NOT invent thresholds not in the question or schema notes '
    '(no absolute sales cutoffs like quantity > 100; no invented feedback-count cutoffs). '
    'Follow Notes: high/high-selling → dynamic median of per-product SUM(quantity) via '
    'MySQL 8 ROW_NUMBER()/COUNT() OVER() (never LIMIT/OFFSET subquery arithmetic); '
    'highest/top/most → ORDER BY total_quantity DESC LIMIT 1 (or equivalent MAX), not median. '
    'Do not hardcode a median. Prefer the simplest valid MySQL; use CTEs only when helpful. '
    'Returns (is_return) are NOT quality issues — use is_return only when the question '
    'explicitly mentions returns. '
    'Return ONLY SQL. No markdown, no explanation. '
    'If the question cannot be answered from the retrieved schema, return exactly: UNSUPPORTED'
)

PRACTICE_QUESTIONS = [
    'What were our total sales this month?',
    'Which products are selling the most?',
    'Can you recommend products for a first-time buyer?',
    'What is the average order value?',
    'Summarize recent customer support queries.',
    'Which category has the highest revenue?',
]

DATA_HINTS = (
    'sales', 'sold', 'selling', 'revenue', 'product', 'products', 'price',
    'quantity', 'order', 'orders', 'total', 'average', 'top', 'best',
    'customer quer', 'support quer', 'how many', 'which product', 'month',
    'stock', 'inventory', 'catalog', 'laptop', 'smartphone', 'headphones',
)


def auth_headers():
    key = os.getenv('HUGGINGFACE_API_KEY') or api_key
    return {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }


def _llm_endpoint():
    """
    Resolve OpenAI-compatible chat-completions URL + model + optional API key.

    Free options:
      LLM_PROVIDER=groq   → free Groq cloud key (https://console.groq.com)
      LLM_PROVIDER=ollama → free local Ollama (no key)
    """
    provider = (os.getenv('LLM_PROVIDER') or LLM_PROVIDER or 'huggingface').strip().lower()

    if provider == 'groq':
        key = os.getenv('GROQ_API_KEY') or ''
        if not key:
            raise RuntimeError(
                'GROQ_API_KEY is not configured. Create a free key at '
                'https://console.groq.com/keys and set GROQ_API_KEY in Backend/.env'
            )
        return {
            'provider': 'groq',
            'url': os.getenv('GROQ_API_URL', GROQ_API_URL),
            'model': os.getenv('GROQ_MODEL', GROQ_MODEL),
            'headers': {
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json',
            },
        }

    if provider == 'ollama':
        return {
            'provider': 'ollama',
            'url': os.getenv('OLLAMA_API_URL', OLLAMA_API_URL),
            'model': os.getenv('OLLAMA_MODEL', OLLAMA_MODEL),
            'headers': {'Content-Type': 'application/json'},
        }

    # Default: Hugging Face Inference Router (often requires paid credits)
    key = os.getenv('HUGGINGFACE_API_KEY') or api_key
    if not key:
        raise RuntimeError(
            'HUGGINGFACE_API_KEY is not configured. For a free setup set '
            'LLM_PROVIDER=groq with GROQ_API_KEY, or LLM_PROVIDER=ollama.'
        )
    return {
        'provider': 'huggingface',
        'url': os.getenv('HF_API_URL', API_URL),
        'model': os.getenv('HF_MODEL', MODEL),
        'headers': auth_headers(),
    }


def get_db_connection():
    return mysql.connector.connect(**db_config)


def call_llm(messages, max_tokens=220, temperature=0.2):
    endpoint = _llm_endpoint()
    logger.info(
        'LLM call | provider=%s | model=%s',
        endpoint['provider'],
        endpoint['model'],
    )
    response = requests.post(
        endpoint['url'],
        headers=endpoint['headers'],
        json={
            'model': endpoint['model'],
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
        },
        timeout=180,
    )
    response.raise_for_status()
    api_response = response.json()

    if isinstance(api_response, dict) and 'error' in api_response:
        raise RuntimeError(str(api_response['error']))

    # TEMP: token-usage diagnostics (OpenAI-compat / Ollama). Remove after measurement.
    if isinstance(api_response, dict):
        usage = api_response.get('usage') or {}
        if usage:
            logger.info(
                'LLM usage | prompt_tokens=%s | completion_tokens=%s | total_tokens=%s | max_tokens=%s',
                usage.get('prompt_tokens'),
                usage.get('completion_tokens'),
                usage.get('total_tokens'),
                max_tokens,
            )
        else:
            logger.info('LLM usage | (no usage field in response) | max_tokens=%s', max_tokens)

    choices = api_response.get('choices') if isinstance(api_response, dict) else None
    if choices:
        message = choices[0].get('message') or {}
        content = (message.get('content') or '').strip()
        if content:
            return content

    raise RuntimeError('Unexpected response format from the agent')


def looks_like_data_question(query_text):
    q = query_text.lower()
    return any(hint in q for hint in DATA_HINTS)


def extract_sql(text):
    if not text:
        return None

    fenced = re.search(r'```(?:sql)?\s*(.*?)```', text, re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    else:
        match = re.search(r'(SELECT\b[\s\S]+)', text, re.IGNORECASE)
        candidate = match.group(1).strip() if match else text.strip()

    candidate = candidate.strip().rstrip(';').strip()
    if not candidate:
        return None

    # Keep only first statement
    candidate = candidate.split(';')[0].strip()
    return candidate


def _strip_leading_sql_noise(sql: str) -> str:
    """Remove leading whitespace and SQL comments (-- and /* */) before validation."""
    text = sql or ''
    while True:
        text = text.lstrip()
        if text.startswith('/*'):
            end = text.find('*/')
            if end == -1:
                return ''
            text = text[end + 2 :]
            continue
        if text.startswith('--'):
            nl = text.find('\n')
            if nl == -1:
                return ''
            text = text[nl + 1 :]
            continue
        break
    # Also strip remaining block/line comments inside for keyword scans later
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.DOTALL)
    text = re.sub(r'--.*?$', ' ', text, flags=re.MULTILINE)
    return text.strip()


def _skip_sql_string(text: str, pos: int) -> int:
    """Advance past a quoted string starting at pos. Returns new index."""
    n = len(text)
    quote = text[pos]
    pos += 1
    while pos < n:
        ch = text[pos]
        if ch == '\\':
            pos += 2
            continue
        if ch == quote:
            # SQL doubled-quote escape: '' or ""
            if pos + 1 < n and text[pos + 1] == quote:
                pos += 2
                continue
            return pos + 1
        pos += 1
    return n


def _skip_balanced_parens(text: str, pos: int) -> int:
    """text[pos] must be '('. Returns index just after the matching ')'."""
    n = len(text)
    if pos >= n or text[pos] != '(':
        return pos
    depth = 1
    pos += 1
    while pos < n and depth:
        ch = text[pos]
        if ch in ("'", '"', '`'):
            pos = _skip_sql_string(text, pos)
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        pos += 1
    return pos


def _with_outer_keyword(sql: str) -> str | None:
    """
    For a WITH query, return the outer statement keyword after CTE definitions
    (select / insert / update / delete / ...). None if unparseable.
    """
    text = sql.strip()
    low = text.lower()
    if not low.startswith('with'):
        return None

    pos = 4
    n = len(text)

    while pos < n:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n:
            return None

        # optional RECURSIVE (once at the start of the CTE list)
        if low.startswith('recursive', pos):
            pos += 9
            while pos < n and text[pos].isspace():
                pos += 1

        # CTE name (allow backticks/quotes)
        if pos < n and text[pos] in ('`', '"', "'"):
            pos = _skip_sql_string(text, pos)
        else:
            while pos < n and (text[pos].isalnum() or text[pos] in '._$'):
                pos += 1

        while pos < n and text[pos].isspace():
            pos += 1

        # optional column list
        if pos < n and text[pos] == '(':
            pos = _skip_balanced_parens(text, pos)
            while pos < n and text[pos].isspace():
                pos += 1

        if not low.startswith('as', pos):
            return None
        pos += 2
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n or text[pos] != '(':
            return None
        pos = _skip_balanced_parens(text, pos)
        while pos < n and text[pos].isspace():
            pos += 1

        if pos < n and text[pos] == ',':
            pos += 1
            continue

        rest = low[pos:].lstrip()
        match = re.match(
            r'(select|insert|update|delete|replace|drop|alter|truncate|create|grant|revoke|with|call|exec)\b',
            rest,
        )
        return match.group(1) if match else None

    return None


def is_safe_select(sql):
    """
    Allow read-only SELECT queries, including read-only CTEs (WITH ... SELECT).
    Reject write/destructive statements, including WITH ... INSERT/UPDATE/DELETE.
    """
    if not sql:
        return False

    cleaned = _strip_leading_sql_noise(sql)
    if not cleaned:
        return False

    normalized = re.sub(r'\s+', ' ', cleaned).strip()
    lower = normalized.lower()

    if lower.startswith('select'):
        outer = 'select'
    elif lower.startswith('with'):
        outer = _with_outer_keyword(cleaned)
        if outer != 'select':
            return False
    else:
        return False

    banned = [
        r'\binsert\b', r'\bupdate\b', r'\bdelete\b', r'\bdrop\b', r'\balter\b',
        r'\btruncate\b', r'\bcreate\b', r'\breplace\b', r'\bgrant\b', r'\brevoke\b',
        r'\binto\s+outfile\b', r'\bload_file\b', r'\bcall\b', r'\bexec\b',
    ]
    if any(re.search(p, lower) for p in banned):
        return False

    return True


def serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def execute_sql_query(sql_query):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql_query)
        rows = cursor.fetchall() or []
        return [{k: serialize_value(v) for k, v in row.items()} for row in rows]
    finally:
        cursor.close()
        conn.close()


def generate_sql(query_text):
    """
    NL→SQL with Schema RAG:
      question → schema_rag.retrieve → schema context → Qwen → SQL

    Returns (sql_or_none, schema_rag_meta_dict).
    """
    model = os.getenv('HF_MODEL', MODEL)
    logger.info('SQL generation start | model=%s | question=%s', model, query_text)

    schema_rag = get_schema_rag()
    retrieval = schema_rag.retrieve(query_text)
    schema_context = retrieval['schema_context']
    schema_meta = {
        'retrieved_tables': retrieval['retrieved_tables'],
        'expanded_tables': retrieval['expanded_tables'],
        'scores': retrieval['scores'],
        'schema_context': schema_context,
    }

    messages = [
        {
            'role': 'system',
            'content': SQL_GENERATION_SYSTEM_PROMPT,
        },
        {
            'role': 'user',
            'content': f'{schema_context}\n\nQuestion: {query_text}\nSQL:',
        },
    ]
    # Median / multi-join analytics questions need a bit more room than simple aggregates.
    raw = call_llm(messages, max_tokens=320, temperature=0.1)
    logger.info('SQL model raw output | %s', raw)

    if 'UNSUPPORTED' in raw.upper() and 'SELECT' not in raw.upper():
        logger.info('SQL generation result | unsupported for question=%s', query_text)
        return None, schema_meta

    sql = extract_sql(raw)
    if not is_safe_select(sql):
        logger.warning('SQL rejected as unsafe | extracted=%s', sql)
        return None, schema_meta

    logger.info('SQL generated | %s', sql)
    return sql, schema_meta


def explain_rows(query_text, sql, rows):
    preview = json.dumps(rows[:15], default=str)
    logger.info('Explain start | rows=%s | sql=%s', len(rows), sql)
    messages = [
        {
            'role': 'system',
            'content': (
                'You are a retail analytics assistant. Using the SQL result JSON, '
                'answer the user clearly in 2-5 short sentences. '
                'Mention key numbers. Do not invent rows that are not present.'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Question: {query_text}\n'
                f'SQL: {sql}\n'
                f'Result rows ({len(rows)} total, showing up to 15): {preview}'
            ),
        },
    ]
    answer = call_llm(messages, max_tokens=220, temperature=0.3)
    logger.info('Explain response | %s', answer)
    return answer


def ask_chat_agent(query_text):
    logger.info('Chat agent start | question=%s', query_text)
    answer = call_llm(
        [
            {'role': 'system', 'content': CHAT_SYSTEM_PROMPT},
            {'role': 'user', 'content': query_text},
        ],
        max_tokens=180,
        temperature=0.6,
    )
    logger.info('Chat agent response | %s', answer)
    return answer


def answer_query(query_text):
    logger.info('--- New query --- | %s', query_text)
    model = os.getenv('HF_MODEL', MODEL)

    def with_pipeline(result, steps):
        result['pipeline'] = steps
        result['model'] = model
        return result

    if looks_like_data_question(query_text):
        sql, schema_meta = generate_sql(query_text)
        schema_tables = schema_meta.get('expanded_tables') or schema_meta.get('retrieved_tables') or []
        schema_scores = schema_meta.get('scores') or {}
        schema_detail = (
            f"tables={', '.join(schema_tables)}; "
            f"scores={json.dumps(schema_scores)}"
        )
        if sql:
            rows = execute_sql_query(sql)
            logger.info('SQL executed | row_count=%s | preview=%s', len(rows), json.dumps(rows[:5], default=str))
            base_steps = [
                {'id': 1, 'title': 'User question', 'status': 'done', 'detail': query_text},
                {
                    'id': 2,
                    'title': 'Schema RAG',
                    'status': 'done',
                    'detail': schema_detail,
                },
                {
                    'id': 3,
                    'title': 'AI → SQL',
                    'status': 'done',
                    'detail': sql,
                    'model': model,
                },
                {
                    'id': 4,
                    'title': 'Run SQL on MySQL',
                    'status': 'done',
                    'detail': f'{len(rows)} row(s) returned',
                },
            ]
            if not rows:
                answer = 'I ran that against the database, but no matching rows were found.'
                logger.info('Final response | %s', answer)
                return with_pipeline(
                    {
                        'answer': answer,
                        'sql': sql,
                        'rows': [],
                        'schema_rag': schema_meta,
                    },
                    base_steps
                    + [
                        {
                            'id': 5,
                            'title': 'AI answer',
                            'status': 'done',
                            'detail': answer,
                            'model': model,
                        }
                    ],
                )
            try:
                explanation = explain_rows(query_text, sql, rows)
            except Exception as exc:
                logger.exception('Explain failed, falling back to raw rows | %s', exc)
                explanation = (
                    f'Here are the results from the database ({len(rows)} row(s)): '
                    f'{json.dumps(rows[:10], default=str)}'
                )
            logger.info('Final response | sql=%s | answer=%s', sql, explanation)
            return with_pipeline(
                {
                    'answer': explanation,
                    'sql': sql,
                    'rows': rows[:50],
                    'schema_rag': schema_meta,
                },
                base_steps
                + [
                    {
                        'id': 5,
                        'title': 'AI answer from results',
                        'status': 'done',
                        'detail': explanation,
                        'model': model,
                    }
                ],
            )

        if re.search(r'\b(stock|inventory)\b', query_text.lower()):
            answer = (
                'Stock/inventory levels are not stored in the current database. '
                'I can help with sales totals, top products, prices, and recent support queries.'
            )
            logger.info('Final response | %s', answer)
            return with_pipeline(
                {'answer': answer, 'sql': None, 'rows': [], 'schema_rag': schema_meta},
                [
                    {'id': 1, 'title': 'User question', 'status': 'done', 'detail': query_text},
                    {
                        'id': 2,
                        'title': 'Schema RAG',
                        'status': 'done',
                        'detail': schema_detail,
                    },
                    {
                        'id': 3,
                        'title': 'AI → SQL',
                        'status': 'skipped',
                        'detail': 'Schema has no stock/inventory fields',
                        'model': model,
                    },
                    {
                        'id': 4,
                        'title': 'AI answer',
                        'status': 'done',
                        'detail': answer,
                        'model': model,
                    },
                ],
            )

    chat = ask_chat_agent(query_text)
    logger.info('Final response | %s', chat)
    return with_pipeline(
        {'answer': chat, 'sql': None, 'rows': []},
        [
            {'id': 1, 'title': 'User question', 'status': 'done', 'detail': query_text},
            {
                'id': 2,
                'title': 'AI chat response',
                'status': 'done',
                'detail': chat,
                'model': model,
            },
        ],
    )


def save_query(query_text, answer):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO customer_queries (query_text, response) VALUES (%s, %s)',
            (query_text, answer),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f'Error saving query: {e}')


@app.route('/sales', methods=['GET'])
def get_sales_data():
    try:
        return jsonify(execute_sql_query('SELECT * FROM sales'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/products', methods=['GET'])
def get_queries():
    try:
        return jsonify(execute_sql_query('SELECT * FROM products'))
    except Exception as e:
        print(f'Error fetching queries: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/practice-questions', methods=['GET'])
def practice_questions():
    return jsonify({'questions': PRACTICE_QUESTIONS})


@app.route('/query', methods=['POST', 'OPTIONS'])
def query():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'CORS Preflight OK'}), 200

    data = request.get_json() or {}
    query_text = data.get('query')

    if not query_text or not isinstance(query_text, str):
        return jsonify({'error': 'Invalid input'}), 400

    query_text = query_text.strip()
    if not query_text:
        return jsonify({'error': 'Invalid input'}), 400

    try:
        result = answer_query(query_text)
        save_query(query_text, result['answer'])
        return jsonify(result)
    except requests.exceptions.HTTPError as e:
        detail = e.response.text if e.response is not None else str(e)
        if e.response is not None and e.response.status_code in (401, 402, 403, 503):
            detail = (
                'The LLM API rejected the request (auth/credits). '
                'For a free setup: set LLM_PROVIDER=groq and GROQ_API_KEY '
                '(https://console.groq.com/keys), or use LLM_PROVIDER=ollama locally. '
                'Hugging Face Inference Router often requires paid credits.'
            )
        return jsonify({'error': detail}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def home():
    return 'Server is running!'


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    app.run(host='0.0.0.0', debug=os.getenv('FLASK_DEBUG') == '1', port=port)
