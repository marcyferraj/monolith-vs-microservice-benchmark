import time
from flask import Flask, jsonify, request
import psycopg2
import requests

app = Flask(__name__)

AUTH_SERVICE_URL = "http://auth-service:5001"
CATALOG_SERVICE_URL = "http://catalog-service:5002"
REQUEST_TIMEOUT = 5

def get_db_connection():
    return psycopg2.connect(host="order_db", database="postgres", user="postgres", password="password")

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "order-service"})

@app.route('/orders')
def orders():
    start_time = time.time()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT order_id, user_id, product_id, total_amount FROM orders;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"ORDER-SERVICE /orders: {execution_time:.4f}s")
    
    return jsonify({
        "orders": rows,
        "latency_seconds": execution_time,
        "service": "order-service"
    })

@app.route('/checkout', methods=['POST'])
def checkout():
    """
    Multi-step distributed operation:
    1. Call auth-service to verify user (HTTP)
    2. Call catalog-service to look up product (HTTP)
    3. Call catalog-service to decrement stock (HTTP)
    4. Insert order into local database
    
    Each network call adds latency and a potential failure point.
    There is NO distributed transaction - if step 4 fails after step 3,
    we have to issue a compensating action to put the stock back.
    """
    start_time = time.time()
    
    data = request.get_json() or {}
    user_id = data.get('user_id', 1)
    product_id = data.get('product_id', 1)
    
    # Step 1: Verify user via auth service (network call #1)
    try:
        auth_response = requests.get(
            f"{AUTH_SERVICE_URL}/users/{user_id}",
            timeout=REQUEST_TIMEOUT
        )
        if auth_response.status_code != 200:
            return jsonify({"error": "User verification failed", "step": "auth"}), 404
        user_data = auth_response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Auth service unavailable: {str(e)}", "step": "auth"}), 503
    
    # Step 2: Look up product via catalog service (network call #2)
    try:
        product_response = requests.get(
            f"{CATALOG_SERVICE_URL}/products/{product_id}",
            timeout=REQUEST_TIMEOUT
        )
        if product_response.status_code != 200:
            return jsonify({"error": "Product lookup failed", "step": "catalog_lookup"}), 404
        product_data = product_response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Catalog service unavailable: {str(e)}", "step": "catalog_lookup"}), 503
    
    if product_data['stock'] <= 0:
        return jsonify({"error": "Out of stock"}), 409
    
    # Step 3: Decrement stock via catalog service (network call #3)
    try:
        decrement_response = requests.post(
            f"{CATALOG_SERVICE_URL}/products/{product_id}/decrement",
            timeout=REQUEST_TIMEOUT
        )
        if decrement_response.status_code != 200:
            return jsonify({"error": "Stock decrement failed", "step": "decrement"}), 409
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Catalog service unavailable: {str(e)}", "step": "decrement"}), 503
    
    # Step 4: Create order record in local database
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO orders (user_id, product_id, total_amount) VALUES (%s, %s, %s) RETURNING order_id;',
            (user_id, product_id, product_data['price'])
        )
        order_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        # Compensating action: put the stock back since order creation failed
        # This is the "Saga pattern" - eventual consistency through compensation
        try:
            requests.post(
                f"{CATALOG_SERVICE_URL}/products/{product_id}/increment",
                timeout=REQUEST_TIMEOUT
            )
        except:
            # If compensation fails, we have inconsistent state - this is the
            # fundamental data consistency challenge in microservices
            pass
        return jsonify({"error": f"Order creation failed: {str(e)}", "step": "order_insert"}), 500
    
    execution_time = time.time() - start_time
    print(f"ORDER-SERVICE /checkout: {execution_time:.4f}s (3 network calls + 1 db write)")
    
    return jsonify({
        "status": "success",
        "order_id": order_id,
        "user": user_data['username'],
        "product": product_data['name'],
        "amount": product_data['price'],
        "latency_seconds": execution_time,
        "service": "order-service",
        "network_calls": 3
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
