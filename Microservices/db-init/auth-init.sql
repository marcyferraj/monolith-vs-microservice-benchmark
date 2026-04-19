CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL
);

INSERT INTO users (username) VALUES
    ('alice'), ('bob'), ('charlie'), ('dave'), ('eve');
