
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, price INTEGER NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0, description TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL DEFAULT 0, username TEXT,
    source TEXT DEFAULT 'discord', item_id INTEGER REFERENCES items(id),
    qty INTEGER NOT NULL, total INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW());
INSERT INTO items(name,price,stock,description) VALUES('測試商品',100,10,'範例')
ON CONFLICT(name) DO NOTHING;
