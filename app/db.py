import os
import sqlite3
from datetime import datetime
from typing import Optional


def init_db(path: str) -> None:
    # tables + index, only if they aren't there already
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prices (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                code       TEXT    NOT NULL,
                price      REAL    NOT NULL,
                currency   TEXT    NOT NULL DEFAULT 'USD',
                fetched_at TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_prices_code_fetched
                ON prices(code, fetched_at DESC);

            CREATE TABLE IF NOT EXISTS settings (
                code  TEXT NOT NULL,
                key   TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (code, key)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def insert_price(
    conn: sqlite3.Connection,
    code: str,
    price: float,
    currency: str,
    fetched_at: str,
) -> None:
    # fetched_at has to be iso-8601 utc
    conn.execute(
        "INSERT INTO prices (code, price, currency, fetched_at) VALUES (?, ?, ?, ?)",
        (code, price, currency, fetched_at),
    )
    conn.commit()


def query_prices(
    conn: sqlite3.Connection,
    code: str,
    since: datetime,
) -> list[dict]:
    # every price for this code since `since` (utc), newest first
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        "SELECT price, currency, fetched_at FROM prices "
        "WHERE code = ? AND fetched_at >= ? ORDER BY fetched_at DESC",
        (code, since_str),
    )
    return [dict(row) for row in cursor.fetchall()]


def count_prices(conn: sqlite3.Connection, code: str, since: datetime) -> int:
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        "SELECT COUNT(*) AS cnt FROM prices WHERE code = ? AND fetched_at >= ?",
        (code, since_str),
    )
    row = cursor.fetchone()
    return row["cnt"] if row else 0


def get_recent_change_timestamps(
    conn: sqlite3.Connection, code: str, n: int = 10
) -> list[str]:
    # fetched_at for the last N rows where the price actually moved. feeds the
    # adaptive scheduler - average the gaps between these and you know roughly
    # how often this commodity is worth re-checking.
    cursor = conn.execute(
        """
        SELECT fetched_at, price FROM prices
        WHERE code = ?
        ORDER BY fetched_at DESC
        LIMIT 200
        """,
        (code,),
    )
    rows = cursor.fetchall()
    change_times: list[str] = []
    prev_price = None
    for row in rows:
        if prev_price is not None and row["price"] != prev_price:
            change_times.append(row["fetched_at"])
            if len(change_times) >= n:
                break
        prev_price = row["price"]
    return change_times


def get_setting(conn: sqlite3.Connection, code: str, key: str) -> Optional[str]:
    cursor = conn.execute(
        "SELECT value FROM settings WHERE code = ? AND key = ?",
        (code, key),
    )
    row = cursor.fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, code: str, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (code, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(code, key) DO UPDATE SET value = excluded.value",
        (code, key, str(value)),
    )
    conn.commit()
