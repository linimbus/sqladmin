"""Create a demo SQLite database used by the SQL Station UI.

Usage:
    python backend/scripts/seed_demo.py [--force]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR  # noqa: E402

SCHEMA = """
DROP VIEW IF EXISTS v_order_summary;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    city TEXT,
    vip INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT,
    price NUMERIC(10, 2) NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    metadata TEXT
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL DEFAULT 'pending',
    total NUMERIC(10, 2) NOT NULL DEFAULT 0,
    ordered_at TEXT NOT NULL
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);

CREATE VIEW v_order_summary AS
SELECT
    o.id AS order_id,
    c.name AS customer_name,
    o.status,
    o.total,
    o.ordered_at,
    COUNT(i.id) AS item_count
FROM orders o
JOIN customers c ON c.id = o.customer_id
LEFT JOIN order_items i ON i.order_id = o.id
GROUP BY o.id, c.name, o.status, o.total, o.ordered_at;
"""

CUSTOMERS = [
    ("张伟", "zhangwei@example.com", "上海", 1),
    ("李娜", "lina@example.com", "北京", 1),
    ("王强", "wangqiang@example.com", "深圳", 0),
    ("陈静", "chenjing@example.com", "杭州", 0),
    ("刘洋", "liuyang@example.com", "成都", 1),
]

PRODUCTS = [
    ("SKU-1001", "机械键盘", "外设", 499.00, 120, '{"color": "black", "switch": "red"}'),
    ("SKU-1002", "人体工学鼠标", "外设", 289.00, 86, '{"dpi": 4000}'),
    ("SKU-2001", "27 寸 4K 显示器", "显示设备", 2199.00, 32, '{"panel": "IPS"}'),
    ("SKU-2002", "USB-C 扩展坞", "配件", 359.00, 64, "{}"),
    ("SKU-3001", "降噪耳机", "音频", 1299.00, 18, '{"anc": true}'),
    ("SKU-3002", "桌面音箱", "音频", 699.00, 45, "{}"),
]

ORDERS = [
    (1, "paid", 998.00),
    (2, "pending", 2199.00),
    (3, "paid", 359.00),
    (4, "cancelled", 1299.00),
    (5, "paid", 1588.00),
    (1, "paid", 289.00),
]

ITEMS = [
    (1, 1, 1, 499.00),
    (1, 1, 2, 289.00),
    (2, 3, 1, 2199.00),
    (3, 4, 1, 359.00),
    (4, 5, 1, 1299.00),
    (5, 1, 1, 499.00),
    (5, 6, 1, 699.00),
    (6, 2, 1, 289.00),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a demo SQLite database.")
    parser.add_argument("--force", action="store_true", help="Overwrite the existing demo.db")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / "demo.db"
    if target.exists() and not args.force:
        print(f"{target} already exists, use --force to overwrite.")
        return

    connection = sqlite3.connect(target)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO customers (name, email, city, vip) VALUES (?, ?, ?, ?)",
            CUSTOMERS,
        )
        connection.executemany(
            "INSERT INTO products (sku, name, category, price, stock, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            PRODUCTS,
        )
        start = datetime.now() - timedelta(days=20)
        connection.executemany(
            "INSERT INTO orders (customer_id, status, total, ordered_at) VALUES (?, ?, ?, ?)",
            [
                (
                    customer_id,
                    status,
                    total,
                    (start + timedelta(days=index * 3, hours=index * 2)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                )
                for index, (customer_id, status, total) in enumerate(ORDERS)
            ],
        )
        connection.executemany(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
            ITEMS,
        )
        connection.commit()
    finally:
        connection.close()

    print(f"Demo database created: {target}")
    print("Create a SQLite connection in SQL Station with path: demo.db")


if __name__ == "__main__":
    main()
