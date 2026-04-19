CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (username) VALUES
    ('alice'), ('bob'), ('charlie'), ('dave'), ('eve');

INSERT INTO products (name, price, stock) VALUES
    ('The Pragmatic Programmer', 39.99, 100),
    ('Clean Code', 34.99, 100),
    ('Designing Data-Intensive Applications', 49.99, 100),
    ('Building Microservices', 44.99, 100),
    ('The Mythical Man-Month', 29.99, 100);