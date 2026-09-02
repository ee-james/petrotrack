import sqlite3
from datetime import datetime, timedelta
from typing import Optional


def compute_metrics(
    conn: sqlite3.Connection,
    code: str,
    alert_threshold: float,
) -> Optional[dict]:
    # everything the front end needs to draw one commodity: latest price, the
    # 24h/30d high-low bands, % change vs a 24h-ago baseline, day-open, and
    # whether that move is big enough to trip the alert. None if we have no
    # rows for this code yet.
    now = datetime.utcnow()
    cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    since_24h  = cutoff_24h          # same cutoff, reused by the high/low queries
    since_30d  = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # latest price
    cursor = conn.execute(
        "SELECT price, currency, fetched_at FROM prices "
        "WHERE code = ? ORDER BY fetched_at DESC LIMIT 1",
        (code,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    current    = row["price"]
    currency   = row["currency"]
    fetched_at = row["fetched_at"]

    # baseline for % change: newest row at or before 24h ago. if there isn't
    # one (code was just added, sparse history) fall back to the oldest row we
    # have so there's always some number to show.
    cursor = conn.execute(
        "SELECT price, fetched_at FROM prices "
        "WHERE code = ? AND fetched_at <= ? "
        "ORDER BY fetched_at DESC LIMIT 1",
        (code, cutoff_24h),
    )
    baseline = cursor.fetchone()

    if baseline is None:
        cursor = conn.execute(
            "SELECT price, fetched_at FROM prices "
            "WHERE code = ? AND fetched_at < ? "
            "ORDER BY fetched_at ASC LIMIT 1",
            (code, fetched_at),
        )
        baseline = cursor.fetchone()

    price_previous: Optional[float]    = None
    fetched_at_previous: Optional[str] = None
    pct_change: Optional[float]        = None
    alert = False

    is_count = (currency == "COUNT")
    count_change: Optional[int] = None

    if baseline is not None:
        price_previous      = baseline["price"]
        fetched_at_previous = baseline["fetched_at"]
        if is_count:
            count_change = int(round(current - price_previous))
            alert = abs(count_change) >= alert_threshold
        elif price_previous != 0:
            pct_change = round((current - price_previous) / price_previous * 100, 4)
            alert = abs(pct_change) >= alert_threshold

    # 24h high/low
    cursor = conn.execute(
        "SELECT MAX(price) AS high, MIN(price) AS low FROM prices "
        "WHERE code = ? AND fetched_at >= ?",
        (code, since_24h),
    )
    row_24h = cursor.fetchone()
    high_24h: Optional[float] = row_24h["high"] if row_24h else None
    low_24h: Optional[float] = row_24h["low"] if row_24h else None

    # 30d high/low
    cursor = conn.execute(
        "SELECT MAX(price) AS high, MIN(price) AS low FROM prices "
        "WHERE code = ? AND fetched_at >= ?",
        (code, since_30d),
    )
    row_30d = cursor.fetchone()
    high_30d: Optional[float] = row_30d["high"] if row_30d else None
    low_30d: Optional[float] = row_30d["low"] if row_30d else None

    # day-open: first price recorded since 00:00 utc today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        "SELECT price FROM prices WHERE code = ? AND fetched_at >= ? ORDER BY fetched_at ASC LIMIT 1",
        (code, today_start),
    )
    open_row = cursor.fetchone()
    open_price: Optional[float] = open_row["price"] if open_row else None

    return {
        "code": code,
        "price": current,
        "currency": currency,
        "is_count": is_count,
        "price_previous": price_previous,
        "fetched_at_previous": fetched_at_previous,
        "pct_change": pct_change,
        "count_change": count_change,
        "high_24h": high_24h,
        "low_24h": low_24h,
        "high_30d": high_30d,
        "low_30d": low_30d,
        "alert": alert,
        "alert_threshold": alert_threshold,
        "fetched_at": fetched_at,
        "open_price": open_price,
    }
