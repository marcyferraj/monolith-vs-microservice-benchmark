import time
from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(host="catalog_db", database="postgres", user="postgres", password="password")

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "catalog-service"})

@app.route('/products')
def products():
    start_time = time.time()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT product_id, name, price, stock FROM products;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"CATALOG-SERVICE /products: {execution_time:.4f}s")
    
    return jsonify({
        "items": rows,
        "latency_seconds": execution_time,
        "service": "catalog-service"
    })

@app.route('/products/<int:product_id>')
def get_product(product_id):
    """Used by order service during checkout to look up product details."""
    start_time = time.time()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT product_id, name, price, stock FROM products WHERE product_id = %s;', (product_id,))
    product = cur.fetchone()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"CATALOG-SERVICE /products/{product_id}: {execution_time:.4f}s")
    
    if not product:
        return jsonify({"error": "Product not found"}), 404
    
    return jsonify({
        "product_id": product[0],
        "name": product[1],
        "price": float(product[2]),
        "stock": product[3],
        "latency_seconds": execution_time,
        "service": "catalog-service"
    })

@app.route('/products/<int:product_id>/decrement', methods=['POST'])
def decrement_stock(product_id):
    """
    Decrement stock by 1. Called by order service during checkout.
    NOTE: This is where eventual consistency problems show up - the catalog
    service has no knowledge of whether the order was actually created.
    """
    start_time = time.time()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Use FOR UPDATE to lock within this database, but this lock does NOT
    # extend across to the order service's database
    cur.execute('SELECT stock FROM products WHERE product_id = %s FOR UPDATE;', (product_id,))
    row = cur.fetchone()
    
    if not row:
        conn.rollback()
        conn.close()
        return jsonify({"error": "Product not found"}), 404
    
    if row[0] <= 0:
        conn.rollback()
        conn.close()
        return jsonify({"error": "Out of stock"}), 409
    
    cur.execute('UPDATE products SET stock = stock - 1 WHERE product_id = %s;', (product_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"CATALOG-SERVICE /products/{product_id}/decrement: {execution_time:.4f}s")
    
    return jsonify({
        "status": "decremented",
        "product_id": product_id,
        "remaining_stock": row[0] - 1,
        "latency_seconds": execution_time,
        "service": "catalog-service"
    })

@app.route('/products/<int:product_id>/increment', methods=['POST'])
def increment_stock(product_id):
    """Compensating action - called if order creation fails after stock was decremented."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE products SET stock = stock + 1 WHERE product_id = %s;', (product_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "incremented", "product_id": product_id})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
