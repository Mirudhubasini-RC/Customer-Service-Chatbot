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
API_URL = os.getenv(
    'HF_API_URL',
    'https://router.huggingface.co/v1/chat/completions',
)
MODEL = os.getenv('HF_MODEL', 'Qwen/Qwen2.5-Coder-7B-Instruct:cheapest')

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

SCHEMA_PROMPT = f"""
MySQL database: {os.getenv('DB_NAME', 'salesdb')}

Tables:
1) products(
     product_id INT PRIMARY KEY,
     product_name VARCHAR(100),
     price DECIMAL(10,2)
   )
2) sales(
     sale_id INT PRIMARY KEY,
     product_id INT,  -- joins to products.product_id
     sale_date DATE,
     quantity INT,
     total_price DECIMAL(10,2)
   )
3) customer_queries(
     query_id INT PRIMARY KEY,
     query_text TEXT,
     response TEXT,
     query_date TIMESTAMP
   )

Notes:
- There is NO stock/inventory column. If asked about stock, say that stock data is unavailable.
- Prefer JOINs between sales and products when product names are needed.
- Use MySQL syntax only.
""".strip()

CHAT_SYSTEM_PROMPT = (
    'You are a friendly retail customer support assistant for RetailAsk. '
    'Answer clearly in 2-4 short sentences. '
    'Help with products, sales, recommendations, and support. '
    'Do not invent exact database numbers.'
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


def get_db_connection():
    return mysql.connector.connect(**db_config)


def call_llm(messages, max_tokens=220, temperature=0.2):
    key = os.getenv('HUGGINGFACE_API_KEY') or api_key
    if not key:
        raise RuntimeError('HUGGINGFACE_API_KEY is not configured')

    model = os.getenv('HF_MODEL', MODEL)
    response = requests.post(
        API_URL,
        headers=auth_headers(),
        json={
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
        },
        timeout=90,
    )
    response.raise_for_status()
    api_response = response.json()

    if isinstance(api_response, dict) and 'error' in api_response:
        raise RuntimeError(str(api_response['error']))

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


def is_safe_select(sql):
    if not sql:
        return False

    normalized = re.sub(r'\s+', ' ', sql).strip()
    lower = normalized.lower()

    if not lower.startswith('select'):
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
    model = os.getenv('HF_MODEL', MODEL)
    logger.info('SQL generation start | model=%s | question=%s', model, query_text)
    messages = [
        {
            'role': 'system',
            'content': (
                'You convert retail questions into a single MySQL SELECT query. '
                'Return ONLY SQL. No markdown, no explanation. '
                'If the question cannot be answered from the schema, return exactly: UNSUPPORTED'
            ),
        },
        {
            'role': 'user',
            'content': f'{SCHEMA_PROMPT}\n\nQuestion: {query_text}\nSQL:',
        },
    ]
    raw = call_llm(messages, max_tokens=180, temperature=0.1)
    logger.info('SQL model raw output | %s', raw)

    if 'UNSUPPORTED' in raw.upper() and 'SELECT' not in raw.upper():
        logger.info('SQL generation result | unsupported for question=%s', query_text)
        return None

    sql = extract_sql(raw)
    if not is_safe_select(sql):
        logger.warning('SQL rejected as unsafe | extracted=%s', sql)
        return None

    logger.info('SQL generated | %s', sql)
    return sql


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
        sql = generate_sql(query_text)
        if sql:
            rows = execute_sql_query(sql)
            logger.info('SQL executed | row_count=%s | preview=%s', len(rows), json.dumps(rows[:5], default=str))
            base_steps = [
                {'id': 1, 'title': 'User question', 'status': 'done', 'detail': query_text},
                {
                    'id': 2,
                    'title': 'AI → SQL',
                    'status': 'done',
                    'detail': sql,
                    'model': model,
                },
                {
                    'id': 3,
                    'title': 'Run SQL on MySQL',
                    'status': 'done',
                    'detail': f'{len(rows)} row(s) returned',
                },
            ]
            if not rows:
                answer = 'I ran that against the database, but no matching rows were found.'
                logger.info('Final response | %s', answer)
                return with_pipeline(
                    {'answer': answer, 'sql': sql, 'rows': []},
                    base_steps
                    + [
                        {
                            'id': 4,
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
                {'answer': explanation, 'sql': sql, 'rows': rows[:50]},
                base_steps
                + [
                    {
                        'id': 4,
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
                {'answer': answer, 'sql': None, 'rows': []},
                [
                    {'id': 1, 'title': 'User question', 'status': 'done', 'detail': query_text},
                    {
                        'id': 2,
                        'title': 'AI → SQL',
                        'status': 'skipped',
                        'detail': 'Schema has no stock/inventory fields',
                        'model': model,
                    },
                    {
                        'id': 3,
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
        if e.response is not None and e.response.status_code in (401, 403):
            detail = (
                'Hugging Face rejected the API key. '
                'Update HUGGINGFACE_API_KEY in Backend/.env with a valid token '
                'that has Inference Providers access.'
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
