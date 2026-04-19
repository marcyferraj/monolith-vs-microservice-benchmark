import time
from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(host="auth_db", database="postgres", user="postgres", password="password")

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "auth-service"})

@app.route('/auth')
def auth():
    start_time = time.time()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT user_id, username FROM users LIMIT 1;')
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"AUTH-SERVICE /auth: {execution_time:.4f}s")
    
    return jsonify({
        "status": "authenticated",
        "user_id": user[0] if user else None,
        "user": user[1] if user else "guest",
        "latency_seconds": execution_time,
        "service": "auth-service"
    })

@app.route('/users/<int:user_id>')
def get_user(user_id):
    """Used by order service during checkout to verify user exists."""
    start_time = time.time()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT user_id, username FROM users WHERE user_id = %s;', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    execution_time = time.time() - start_time
    print(f"AUTH-SERVICE /users/{user_id}: {execution_time:.4f}s")
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "user_id": user[0],
        "username": user[1],
        "latency_seconds": execution_time,
        "service": "auth-service"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)