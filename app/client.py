import os
import httpx
from datetime import datetime, timezone

BASE_URL = "https://api.oilpriceapi.com/v1"


class OilPriceClient:
    def __init__(self):
        api_key = os.getenv("OIL_PRICE_API")
        if not api_key:
            raise RuntimeError("OIL_PRICE_API environment variable not set")
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    async def fetch_commodities(self) -> list[str]:
        # the full catalog of codes the api knows about, plan or no plan
        url = f"{BASE_URL}/commodities"
        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.get(url, headers=self.headers)
            response.raise_for_status()
            body = response.json()
        raw = body.get("data", {}).get("commodities", [])
        if isinstance(raw, list):
            return [item["code"] for item in raw if isinstance(item, dict) and item.get("code")]
        return []

    async def check_plan_availability(self, codes: list[str]) -> list[str]:
        # which of these codes actually return data on the current plan.
        # api caps a request at 20 codes, so walk it in chunks. sequential
        # on purpose - hammering it in parallel just trips the rate limit.
        CHUNK = 20
        available: list[str] = []

        for i in range(0, len(codes), CHUNK):
            chunk = codes[i:i + CHUNK]
            url = f"{BASE_URL}/prices/latest?by_code={','.join(chunk)}"
            try:
                async with httpx.AsyncClient(timeout=15) as http:
                    r = await http.get(url, headers=self.headers)
                    r.raise_for_status()
                    body = r.json()
                data = body.get("data", {})
                if isinstance(data, dict) and "prices" in data:
                    available.extend(
                        item["code"] for item in data["prices"] if item.get("code")
                    )
                elif isinstance(data, dict) and "price" in data and data.get("code"):
                    available.append(data["code"])
            except Exception as exc:
                print(f"plan-check: chunk {i//CHUNK + 1} failed: {exc}")

        return available

    async def fetch_historical(self, code: str, start_at: str, end_at: str) -> list[dict]:
        # historical prices for one code, oldest first, same dict shape as fetch_price
        url = f"{BASE_URL}/prices/historical?by_code={code}&start_at={start_at}&end_at={end_at}"
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(url, headers=self.headers)
            response.raise_for_status()
            body = response.json()

        if not isinstance(body, dict):
            return []
        raw = body.get("data", [])
        if not isinstance(raw, list):
            return []
        return [
            {
                "code": item.get("code", code),
                "price": float(item["price"]),
                "currency": item.get("currency", "USD"),
                "fetched_at": _normalize_timestamp(item.get("created_at")),
            }
            for item in raw
            if isinstance(item, dict) and item.get("price") is not None
        ]

    async def fetch_prices(
        self,
        codes: list[str],
        known_solo: set[str] | None = None,
    ) -> tuple[list[dict], set[str]]:
        # latest prices for a pile of codes, using as few api calls as possible:
        #   round 1  batches of 20
        #   round 2  whatever dropped out, retried in groups of 10
        #   round 3  still missing? one at a time
        # codes in known_solo skip straight to round 3. we hand back the set of
        # codes that only worked solo this run so the caller can remember them
        # and skip the wasted batch attempts next time.
        CHUNK       = 20
        RETRY_CHUNK = 10
        known_solo  = known_solo or set()

        results:      list[dict] = []
        need_retry:   list[str]  = []               # dropped from the round-1 batches
        solo_fetch:   list[str]  = list(known_solo)  # known solo + whatever we discover
        newly_solo:   set[str]   = set()

        # ---- Round 1: batches of 20, skipping known-solo codes ----
        batch_codes = [c for c in codes if c not in known_solo]
        for i in range(0, len(batch_codes), CHUNK):
            chunk = batch_codes[i:i + CHUNK]
            returned = await self._fetch_chunk(chunk, f"batch chunk {i // CHUNK + 1}")
            results.extend(returned.values())
            dropped = [c for c in chunk if c not in returned]
            if dropped:
                need_retry.extend(dropped)

        # ---- Round 2: retry the dropped ones in groups of 10 ----
        if need_retry:
            print(f"fetch_prices: {len(need_retry)} dropped from batches, retrying in groups of {RETRY_CHUNK}")
            still_missing: list[str] = []
            for i in range(0, len(need_retry), RETRY_CHUNK):
                chunk = need_retry[i:i + RETRY_CHUNK]
                returned = await self._fetch_chunk(chunk, f"retry group {i // RETRY_CHUNK + 1}")
                results.extend(returned.values())
                dropped = [c for c in chunk if c not in returned]
                if dropped:
                    still_missing.extend(dropped)
            if still_missing:
                print(f"fetch_prices: {len(still_missing)} still missing, going solo")
                solo_fetch.extend(c for c in still_missing if c not in known_solo)
                newly_solo.update(still_missing)

        # ---- Round 3: solo fetches ----
        for code in solo_fetch:
            url = f"{BASE_URL}/prices/latest?by_code={code}"
            try:
                async with httpx.AsyncClient(timeout=10) as http:
                    r = await http.get(url, headers=self.headers)
                    r.raise_for_status()
                    body = r.json()
                item = body.get("data", {})
                if isinstance(item, dict) and item.get("price") is not None:
                    results.append({
                        "code": item.get("code", code),
                        "price": float(item["price"]),
                        "currency": item.get("currency", "USD"),
                        "fetched_at": _normalize_timestamp(item.get("created_at")),
                    })
                    print(f"fetch_prices: solo ok {code}")
                else:
                    print(f"fetch_prices: solo no data {code}")
            except Exception as exc:
                print(f"fetch_prices: solo failed {code}: {exc}")

        return results, newly_solo

    async def _fetch_chunk(self, codes: list[str], label: str) -> dict[str, dict]:
        # fetch one batch, return {code: normalized dict} for whatever came back
        url = f"{BASE_URL}/prices/latest?by_code={','.join(codes)}"
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                r = await http.get(url, headers=self.headers)
                r.raise_for_status()
                body = r.json()
        except Exception as exc:
            print(f"fetch_prices: {label} failed: {exc}")
            return {}

        data = body.get("data", {})
        if isinstance(data, dict) and "prices" in data:
            raw = data["prices"]
        elif isinstance(data, dict) and "price" in data:
            raw = [data]
        else:
            return {}

        out: dict[str, dict] = {}
        for item in raw:
            if isinstance(item, dict) and item.get("price") is not None:
                code = item.get("code", codes[0])
                out[code] = {
                    "code": code,
                    "price": float(item["price"]),
                    "currency": item.get("currency", "USD"),
                    "fetched_at": _normalize_timestamp(item.get("created_at")),
                }
        return out

    async def fetch_price(self, code: str) -> dict:
        results, _ = await self.fetch_prices([code])
        if not results:
            raise RuntimeError(f"No data returned for {code!r}")
        return results[0]


def _normalize_timestamp(ts: str | None) -> str:
    # pin an api timestamp to iso-8601 utc. if it's missing or junk, use now.
    if not ts:
        return _now_utc()
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, AttributeError):
        return _now_utc()


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
