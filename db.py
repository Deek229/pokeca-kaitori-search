"""SQLite 接続とスキーマ"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DB_FILE

SCHEMA = """
CREATE TABLE IF NOT EXISTS sets (
    id TEXT PRIMARY KEY,
    tcgdex_id TEXT UNIQUE,
    name TEXT NOT NULL,
    series_name TEXT,
    release_date TEXT,
    card_count_official INTEGER
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    set_id TEXT NOT NULL REFERENCES sets(id),
    tcgdex_id TEXT UNIQUE,
    local_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rarity TEXT,
    image_url TEXT,
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS shops (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    website_url TEXT
);

CREATE TABLE IF NOT EXISTS buyback_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL REFERENCES cards(id),
    shop_id TEXT NOT NULL REFERENCES shops(id),
    price_yen INTEGER NOT NULL,
    condition_note TEXT NOT NULL DEFAULT '美品',
    as_of_date TEXT NOT NULL,
    product_url TEXT,
    UNIQUE(card_id, shop_id, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
CREATE INDEX IF NOT EXISTS idx_cards_local_id ON cards(local_id);
CREATE INDEX IF NOT EXISTS idx_cards_search ON cards(search_text);
CREATE INDEX IF NOT EXISTS idx_buyback_card ON buyback_prices(card_id);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL REFERENCES cards(id),
    shop_id TEXT NOT NULL REFERENCES shops(id),
    price_yen INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    condition_note TEXT NOT NULL DEFAULT '',
    product_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_price_history_card ON price_history(card_id);
CREATE INDEX IF NOT EXISTS idx_price_history_lookup ON price_history(card_id, shop_id, recorded_at);
"""


def ensure_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connect():
    ensure_db()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
