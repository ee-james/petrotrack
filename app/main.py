## @file Implementation for main.
##
import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Any

import httpx
import toml
from fastapi import Body, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.client import OilPriceClient
from app.config_loader import CONFIG_PATH, get_config, load_config
from app.db import (
    count_prices,
    get_recent_change_timestamps,
    get_setting,
    init_db,
    insert_price,
    query_prices,
    set_setting,
)
from app.metrics import compute_metrics

app = FastAPI()
client = OilPriceClient()

## @brief Documents _available_commodities.
##
def _available_commodities() -> list[str]:
    return get_config()["commodities"]["available"]


# ---- DB dependency ----

## @brief Documents get_db.
##
def get_db():
    path = get_config()["database"]["path"]
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---- Startup ----

## @brief Documents on_startup.
##
@app.on_event("startup")
def on_startup():
    # db has to exist before the background loops touch it
    config = get_config()
    init_db(config["database"]["path"])


## @brief Documents start_background_tasks.
##
@app.on_event("startup")
async def start_background_tasks() -> None:
    asyncio.create_task(_config_reload_loop())
    asyncio.create_task(_scheduled_refresh_loop())


## @brief Documents _config_reload_loop.
##
async def _config_reload_loop() -> None:
    # config.toml is hot-reloaded, poll its mtime
    while True:
        await asyncio.sleep(3)
        load_config()


## @brief Documents _backfill_if_needed.
##
async def _backfill_if_needed(conn: sqlite3.Connection, code: str) -> None:
    # grab 30d of history if we have fewer than 2 rows for this code.
    # runs at startup and on every scheduled refresh so a newly added
    # commodity isn't blank for a month. codes that 400'd before are
    # skipped for good to save api calls.
    if get_setting(conn, code, "historical_unsupported"):
        return

    since_30d = datetime.utcnow() - timedelta(days=30)
    if count_prices(conn, code, since_30d) >= 2:
        return

    start = since_30d.strftime("%Y-%m-%dT%H:%M:%SZ")
    end   = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        prices = await client.fetch_historical(code, start, end)
        for p in prices:
            insert_price(conn, p["code"], p["price"], p["currency"], p["fetched_at"])
        print(f"backfill: {code} inserted {len(prices)} rows")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            set_setting(conn, code, "historical_unsupported", "1")
            print(f"backfill: {code} historical not supported, flagged - won't retry")
        else:
            print(f"backfill: {code} failed - {exc}")
    except Exception as exc:
        print(f"backfill: {code} failed - {exc}")


## @brief Documents _scheduled_refresh_loop.
##
async def _scheduled_refresh_loop() -> None:
    while True:
        await _do_scheduled_refresh()
        config = get_config()
        interval_seconds = config["behavior"]["auto_refresh_minutes"] * 60
        print(f"scheduled_refresh: next run in {interval_seconds}s ({config['behavior']['auto_refresh_minutes']}m)")
        await asyncio.sleep(interval_seconds)


_COUNT_CURRENCIES = {"COUNT"}
_REFRESH_FLOOR_S  = 6 * 3600        # never re-check a count code more than every 6h
_REFRESH_CEIL_S   = 30 * 24 * 3600  # ...or less than once a month


## @brief Documents _is_count_code.
##
def _is_count_code(conn: sqlite3.Connection, code: str) -> bool:
    # count codes (rig counts, permits, ...) carry a COUNT currency instead of a price
    row = conn.execute(
        "SELECT currency FROM prices WHERE code = ? ORDER BY fetched_at DESC LIMIT 1",
        (code,),
    ).fetchone()
    return row is not None and row["currency"] in _COUNT_CURRENCIES


## @brief Documents _update_adaptive_schedule.
##
def _update_adaptive_schedule(conn: sqlite3.Connection, code: str) -> None:
    # count codes barely move, so space out the polling based on how often
    # this one has actually changed. sets next_check_at.
    timestamps = get_recent_change_timestamps(conn, code, n=10)
    now = datetime.utcnow()

    if len(timestamps) >= 2:
        # average the gap between real changes, oldest to newest
        dts = sorted(datetime.fromisoformat(t.replace("Z", "")) for t in timestamps)
        gaps = [(dts[i + 1] - dts[i]).total_seconds() for i in range(len(dts) - 1)]
        avg_s = sum(gaps) / len(gaps)
        set_setting(conn, code, "avg_change_interval_s", str(avg_s))
        next_s = max(_REFRESH_FLOOR_S, min(avg_s * 2, _REFRESH_CEIL_S))
    else:
        # not enough change history - fall back to how stale it is
        last_change = get_setting(conn, code, "last_change_at")
        if last_change:
            days_since = (now - datetime.fromisoformat(last_change.replace("Z", ""))).days
        else:
            days_since = 999
        if days_since < 16:
            next_s = 7 * 24 * 3600
        elif days_since < 90:
            next_s = 14 * 24 * 3600
        else:
            next_s = 30 * 24 * 3600

    next_check = (now + timedelta(seconds=next_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    set_setting(conn, code, "next_check_at", next_check)
    print(f"adaptive: {code} next check in {next_s/3600:.1f}h -> {next_check}")


## @brief Documents _do_scheduled_refresh.
##
async def _do_scheduled_refresh() -> None:
    # backfill anything thin on history, then pull latest prices. price codes
    # always get pulled; count codes only when their next_check_at has come up.
    config = get_config()
    all_codes = config["commodities"]["enabled"]
    db_path = config["database"]["path"]
    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        for code in all_codes:
            await _backfill_if_needed(conn, code)

        # price codes every time, count codes only when scheduled
        price_codes = []
        count_codes = []
        for code in all_codes:
            if _is_count_code(conn, code):
                next_check = get_setting(conn, code, "next_check_at")
                if next_check and next_check > now_str:
                    print(f"adaptive: {code} skip, next check at {next_check}")
                    continue
                count_codes.append(code)
            else:
                price_codes.append(code)

        codes_to_fetch = price_codes + count_codes
        if not codes_to_fetch:
            print("scheduled_refresh: all count codes current, nothing to fetch")
            return

        try:
            known_solo = {
                code for code in codes_to_fetch
                if get_setting(conn, code, "solo_only") == "1"
            }
            prices, newly_solo = await client.fetch_prices(codes_to_fetch, known_solo)
            for code in newly_solo:
                set_setting(conn, code, "solo_only", "1")
                print(f"fetch_prices: {code} is solo-only from now on")

            fetched = {p["code"]: p for p in prices}

            for code in codes_to_fetch:
                if code in fetched:
                    p = fetched[code]
                    # need the old price to know if it moved (adaptive scheduler)
                    prev_row = conn.execute(
                        "SELECT price FROM prices WHERE code = ? ORDER BY fetched_at DESC LIMIT 1",
                        (code,),
                    ).fetchone()
                    insert_price(conn, p["code"], p["price"], p["currency"], p["fetched_at"])
                    set_setting(conn, code, "status", "ok")

                    if code in count_codes:
                        if prev_row is None or p["price"] != prev_row["price"]:
                            set_setting(conn, code, "last_change_at", p["fetched_at"])
                        _update_adaptive_schedule(conn, code)
                else:
                    # api didn't return this one - note it, don't blow up
                    existing_status = get_setting(conn, code, "status")
                    if existing_status != "not_on_plan":
                        set_setting(conn, code, "status", "no_data")

            missing = [c for c in codes_to_fetch if c not in fetched]
            if missing:
                print(f"scheduled_refresh: no data for {len(missing)} code(s), "
                      f"probably not on plan: {', '.join(missing)}")
        except Exception as exc:
            print(f"scheduled_refresh: batch fetch failed: {exc}")
    finally:
        conn.close()


# ---- Endpoints ----

## @brief Documents read_config.
##
@app.get("/config")
def read_config():
    return get_config()


## @brief Documents read_metrics.
##
@app.get("/metrics/{code}")
def read_metrics(code: str, conn=Depends(get_db)):
    config = get_config()
    default_threshold = config["behavior"]["default_alert_threshold"]
    raw = get_setting(conn, code, "alert_threshold")
    threshold = float(raw) if raw is not None else default_threshold

    result = compute_metrics(conn, code, threshold)
    if result is None:
        status = get_setting(conn, code, "status") or "no_data"
        raise HTTPException(status_code=404, detail={"status": status})
    return result


## @brief Documents read_prices.
##
@app.get("/prices/{code}")
def read_prices(code: str, conn=Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=30)
    rows = query_prices(conn, code, since)
    return {"code": code, "prices": rows}


## @brief Documents read_settings.
##
@app.get("/settings/{code}")
def read_settings(code: str, conn=Depends(get_db)):
    config = get_config()
    default = config["behavior"]["default_alert_threshold"]
    raw = get_setting(conn, code, "alert_threshold")
    threshold = float(raw) if raw is not None else default
    return {"code": code, "alert_threshold": threshold}


## @brief Documents SettingsBody.
##
class SettingsBody(BaseModel):
    alert_threshold: float


## @brief Documents write_settings.
##
@app.put("/settings/{code}")
def write_settings(code: str, body: SettingsBody, conn=Depends(get_db)):
    set_setting(conn, code, "alert_threshold", body.alert_threshold)
    return {"code": code, "alert_threshold": body.alert_threshold}


# ---- Theme read/write ----

## @brief Documents read_theme.
##
@app.get("/config/theme")
def read_theme():
    return get_config().get("theme", {})


## @brief Documents write_theme.
##
@app.put("/config/theme")
def write_theme(body: dict[str, Any] = Body(...)):
    with open(CONFIG_PATH) as f:
        doc = toml.load(f)
    theme = doc.setdefault("theme", {})
    for section, values in body.items():
        if isinstance(values, dict) and section in theme:
            theme[section].update(values)
    with open(CONFIG_PATH, "w") as f:
        toml.dump(doc, f)
    load_config()
    return doc["theme"]


# ---- Commodity catalog + config write-back ----

## @brief Documents list_available_commodities.
##
@app.get("/commodities/available")
def list_available_commodities():
    return {"codes": _available_commodities()}


## @brief Documents check_commodities_plan.
##
@app.get("/commodities/plan-check")
async def check_commodities_plan():
    # hit the api for every catalog code and see which ones come back with
    # data. not cached - only called when the user asks for a refresh.
    codes = get_config()["commodities"]["available"]
    available = await client.check_plan_availability(codes)
    unavailable = [c for c in codes if c not in available]
    print(f"plan-check: {len(available)} available, {len(unavailable)} unavailable: "
          f"{', '.join(unavailable) if unavailable else 'none'}")

    db_path = get_config()["database"]["path"]
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        for code in unavailable:
            set_setting(conn, code, "status", "not_on_plan")
        for code in available:
            existing = get_setting(conn, code, "status")
            if existing == "not_on_plan":
                set_setting(conn, code, "status", "ok")
    finally:
        conn.close()

    return {"available": available, "unavailable": unavailable}


## @brief Documents fetch_commodities_catalog.
##
@app.get("/commodities/catalog")
async def fetch_commodities_catalog():
    # read-only, doesn't touch config
    codes = await client.fetch_commodities()
    return {"codes": codes}


## @brief Documents CommoditiesBody.
##
class CommoditiesBody(BaseModel):
    enabled: list[str]


## @brief Documents update_enabled_commodities.
##
@app.put("/commodities/enabled")
def update_enabled_commodities(body: CommoditiesBody):
    if not body.enabled:
        raise HTTPException(status_code=400, detail="At least one commodity required")

    with open(CONFIG_PATH) as f:
        doc = toml.load(f)

    # keep whatever's already in `available`, add any new ones being enabled
    existing = doc.get("commodities", {}).get("available", [])
    merged = list(dict.fromkeys(existing + body.enabled))
    doc["commodities"]["available"] = merged
    doc["commodities"]["enabled"] = body.enabled

    with open(CONFIG_PATH, "w") as f:
        toml.dump(doc, f)

    load_config()
    return {"enabled": body.enabled}


## @brief Documents get_last_refresh.
##
@app.get("/last_refresh")
def get_last_refresh(conn=Depends(get_db)):
    # newest fetched_at across everything we're tracking
    config = get_config()
    codes = config["commodities"]["enabled"]
    if not codes:
        return {"last_refresh_at": None}
    placeholders = ",".join("?" * len(codes))
    cursor = conn.execute(
        f"SELECT MAX(fetched_at) AS last FROM prices WHERE code IN ({placeholders})",
        tuple(codes),
    )
    row = cursor.fetchone()
    return {"last_refresh_at": row["last"] if row else None}
