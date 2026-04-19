CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0
);

INSERT INTO products (name, price, stock) VALUES
    ('The Pragmatic Programmer', 39.99, 100),
    ('Clean Code', 34.99, 100),
    ('Designing Data-Intensive Applications', 49.99, 100),
    ('Building Microservices', 44.99, 100),
    ('The Mythical Man-Month', 29.99, 100);
