from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import os

import requests
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

api_key = os.getenv('HUGGINGFACE_API_KEY')
API_URL = 'https://api-inference.huggingface.co/models/EleutherAI/gpt-neox-20b'
HEADERS = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json',
}

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)


# Database connection configuration

# Database connection
db_config = {
    'user': 'root',
    'password': '',
    'host': '127.0.0.1',
    'database': 'salesdb'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)


def get_predefined_query(query):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT sql_query FROM query_patterns WHERE %s LIKE pattern", (query,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['sql_query'] if result else None
    except Exception as e:
        print(f"Error fetching predefined query: {e}")
        return None

def execute_sql_query(sql_query):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql_query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error executing SQL query: {e}")
        return []


@app.route('/sales', methods=['GET'])
def get_sales_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sales")
        sales = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(sales)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/queries', methods=['GET'])
def get_queries():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM customer_queries")
        queries = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(queries)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/query', methods=['POST'])
def handle_query():
    data = request.get_json()
    query = data.get('query')

    if not query or not isinstance(query, str):
        return jsonify({'error': 'Invalid input'}), 400

    try:

        # Send the query to the LLM
        response = requests.post(API_URL, headers=HEADERS, json={'inputs': query})
        response.raise_for_status()
        api_response = response.json()
        
        if isinstance(api_response, list) and 'generated_text' in api_response[0]:
            answer = api_response[0]['generated_text']


            # Check if the query matches predefined patterns for direct SQL queries
            sql_query = get_predefined_query(query)
            if sql_query:
                data_from_db = execute_sql_query(sql_query)
                answer += f" Here is the data from the database: {data_from_db}"
            
            # Insert the query into the database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO customer_queries (query_text, response) VALUES (%s, %s)", (query, answer))
            conn.commit()
            cursor.close()
            conn.close()
            

            # Here you might want to add logic to query your database based on the LLM response

            return jsonify({'answer': answer})
        else:
            return jsonify({'answer': 'Unexpected response format from the API'})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def home():
    return 'Server is running!'

if __name__ == '__main__':
    app.run(debug=True, port=8000)
