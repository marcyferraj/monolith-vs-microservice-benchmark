import time
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="db",
            database="postgres",
            user="postgres",
            password="password"
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

@app.route('/health')
def health():
    return jsonify({"status": "ok", "architecture": "monolith"})

@app.route('/auth')
def auth():
    start_time = time.time()
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database not ready"}), 500
    
    cur = conn.cursor()
    cur.execute('SELECT user_id, username FROM users LIMIT 1;')
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"MONOLITH /auth: {execution_time:.4f}s")
    
    return jsonify({
        "status": "authenticated",
        "user_id": user[0] if user else None,
        "user": user[1] if user else "guest",
        "latency_seconds": execution_time,
        "architecture": "monolith"
    })

@app.route('/products')
def products():
    start_time = time.time()
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database not ready"}), 500
    
    cur = conn.cursor()
    cur.execute('SELECT product_id, name, price, stock FROM products;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"MONOLITH /products: {execution_time:.4f}s")
    
    return jsonify({
        "items": rows,
        "latency_seconds": execution_time,
        "architecture": "monolith"
    })

@app.route('/orders')
def orders():
    start_time = time.time()
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database not ready"}), 500
    
    cur = conn.cursor()
    cur.execute('SELECT order_id, user_id, product_id, total_amount FROM orders;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"MONOLITH /orders: {execution_time:.4f}s")
    
    return jsonify({
        "orders": rows,
        "latency_seconds": execution_time,
        "architecture": "monolith"
    })

@app.route('/checkout', methods=['POST'])
def checkout():
    """
    Multi-step operation: verify user, look up product, decrement stock, create order.
    In the monolith, this is one transaction against one database - all or nothing.
    """
    start_time = time.time()
    
    data = request.get_json() or {}
    user_id = data.get('user_id', 1)
    product_id = data.get('product_id', 1)
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database not ready"}), 500
    
    try:
        cur = conn.cursor()
        
        # Step 1: Verify user exists (auth check)
        cur.execute('SELECT user_id, username FROM users WHERE user_id = %s;', (user_id,))
        user = cur.fetchone()
        if not user:
            conn.rollback()
            return jsonify({"error": "User not found"}), 404
        
        # Step 2: Look up product and check stock (catalog check)
        # SELECT FOR UPDATE locks the row to prevent race conditions
        cur.execute('SELECT product_id, name, price, stock FROM products WHERE product_id = %s FOR UPDATE;', (product_id,))
        product = cur.fetchone()
        if not product:
            conn.rollback()
            return jsonify({"error": "Product not found"}), 404
        
        if product[3] <= 0:
            conn.rollback()
            return jsonify({"error": "Out of stock"}), 409
        
        # Step 3: Decrement stock
        cur.execute('UPDATE products SET stock = stock - 1 WHERE product_id = %s;', (product_id,))
        
        # Step 4: Create order record
        cur.execute(
            'INSERT INTO orders (user_id, product_id, total_amount) VALUES (%s, %s, %s) RETURNING order_id;',
            (user_id, product_id, product[2])
        )
        order_id = cur.fetchone()[0]
        
        # Commit the entire transaction - all steps succeed or all roll back
        conn.commit()
        cur.close()
        conn.close()
        
        execution_time = time.time() - start_time
        print(f"MONOLITH /checkout: {execution_time:.4f}s")
        
        return jsonify({
            "status": "success",
            "order_id": order_id,
            "user": user[1],
            "product": product[1],
            "amount": float(product[2]),
            "latency_seconds": execution_time,
            "architecture": "monolith"
        })
    
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
