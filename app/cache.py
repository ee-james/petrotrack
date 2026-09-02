from datetime import datetime, timedelta

class OilPriceCache:
    def __init__(self):
        self.data = {}
        self.timestamp = {}

    def is_fresh(self, code: str, max_age_minutes: int) -> bool:
        ts = self.timestamp.get(code)
        if not ts:
            return False
        return datetime.utcnow() - ts < timedelta(minutes=max_age_minutes)

    def get(self, code: str):
        return self.data.get(code)

    def set(self, code: str, value: dict):
        self.data[code] = value
        self.timestamp[code] = datetime.utcnow()
