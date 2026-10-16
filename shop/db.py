"""Nebula Gear's SQLite database: schema, seed data (handoff Appendix A.2–A.3) and small helpers."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("SHOP_DB", Path(__file__).parent / "data" / "nebula.db"))

SCHEMA = """
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, slug TEXT, price REAL NULL, image TEXT NULL,
                       category TEXT, on_sale INTEGER, stock INTEGER);
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT);
CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id INTEGER NULL, flash TEXT NULL);
CREATE TABLE carts (id INTEGER PRIMARY KEY, session_id TEXT UNIQUE, user_id INTEGER NULL);
CREATE TABLE cart_items (cart_id INTEGER, product_id INTEGER, qty INTEGER, PRIMARY KEY (cart_id, product_id));
CREATE TABLE coupons (code TEXT PRIMARY KEY, percent REAL, active INTEGER, excludes_sale INTEGER);
CREATE TABLE applied_coupons (cart_id INTEGER PRIMARY KEY, code TEXT, times_applied INTEGER);
CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total REAL, name TEXT, address TEXT, city TEXT,
                     created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE order_items (order_id INTEGER, product_id INTEGER, qty INTEGER, price REAL);
CREATE TABLE wishlist (owner TEXT, product_id INTEGER, PRIMARY KEY (owner, product_id));
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
"""

CATEGORIES = {"telescopes": "Telescopes", "accessories": "Accessories", "maps": "Maps and charts"}

# id, name, price, image, category, on_sale, stock
PRODUCTS = [
    (1, "Mystery Meteorite", 120.00, None, "accessories", 0, 5),
    (2, "Orion 70mm Telescope", 249.00, "/static/img/telescope.svg", "telescopes", 0, 8),
    (3, "Star Atlas", 39.00, "/static/img/atlas.svg", "maps", 0, 20),
    (4, "Red Dot Finder", 29.00, "/static/img/finder.svg", "accessories", 0, 12),
    (5, "Moon Map Poster", 19.00, "/static/img/moon.svg", "maps", 1, 30),
    (6, "Planisphere", 24.00, "/static/img/planisphere.svg", "maps", 0, 15),
    (7, "Eyepiece Kit", 89.00, "/static/img/eyepiece.svg", "accessories", 0, 9),
    (8, "Comet Hunter Binoculars", None, "/static/img/binoculars.svg", "telescopes", 0, 6),
    (9, "Solar Filter", 59.00, "/static/img/filter.svg", "accessories", 0, 0),
    (10, "Astro Camera", 399.00, "/static/img/camera.svg", "telescopes", 0, 4),
    (11, "Tripod", 79.00, "/static/img/tripod.svg", "accessories", 0, 7),
    (12, "Red Flashlight", 15.00, "/static/img/flashlight.svg", "accessories", 0, 25),
]

COUPONS = [("SAVE10", 10.0, 1, 1), ("EXPIRED5", 5.0, 0, 0)]


def hash_password(pw: str) -> str:
    return hashlib.sha256(("nebula:" + pw).encode()).hexdigest()


def explorer_password() -> str:
    return os.environ.get("SHOP_EXPLORER_PASSWORD") or "nebula-pass"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def reset(release: str = "v1") -> None:
    """Drop everything and reseed (POST /__reset)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tables:
        conn.execute(f"DROP TABLE {t}")
    conn.executescript(SCHEMA)
    for pid, name, price, image, cat, sale, stock in PRODUCTS:
        slug = name.lower().replace(" ", "-")
        conn.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?)", (pid, name, slug, price, image, cat, sale, stock))
    pw = hash_password(explorer_password())
    emails = [f"explorer{i}@nebula.test" for i in range(1, 9)] + ["demo@nebula.test"]
    for email in emails:
        conn.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, pw))
    conn.executemany("INSERT INTO coupons VALUES (?,?,?,?)", COUPONS)
    conn.execute("INSERT INTO settings VALUES ('release', ?)", (release,))
    conn.close()


def ensure() -> None:
    if not DB_PATH.exists():
        reset()
