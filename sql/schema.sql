-- Normalised schema: one row per customer, product and order line.
CREATE TABLE customers (
    customer_id   TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    segment       TEXT NOT NULL,          -- Consumer, Corporate, Home Office
    city          TEXT,
    state         TEXT NOT NULL,
    postal_code   TEXT,
    region        TEXT NOT NULL           -- sales territory: West, East, Central, South
);

CREATE TABLE products (
    product_id   TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    sub_category TEXT NOT NULL,
    product_name TEXT NOT NULL
);

CREATE TABLE orders (
    row_id      INTEGER PRIMARY KEY,
    order_id    TEXT NOT NULL,
    order_date  TEXT NOT NULL,            -- ISO yyyy-mm-dd
    ship_date   TEXT NOT NULL,
    ship_mode   TEXT,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    product_id  TEXT NOT NULL REFERENCES products(product_id),
    sales       REAL NOT NULL,
    quantity    INTEGER NOT NULL,
    discount    REAL NOT NULL,
    profit      REAL NOT NULL
);

CREATE TABLE returns (
    order_id TEXT PRIMARY KEY,
    returned TEXT NOT NULL
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_product  ON orders(product_id);
CREATE INDEX idx_orders_date     ON orders(order_date);
