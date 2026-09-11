## @file Implementation for cache.
##
from datetime import datetime, timedelta

## @brief Documents OilPriceCache.
##
class OilPriceCache:
    ## @brief Documents __init__.
    ##
    def __init__(self):
        self.data = {}
        self.timestamp = {}

    ## @brief Documents is_fresh.
    ##
    def is_fresh(self, code: str, max_age_minutes: int) -> bool:
        ts = self.timestamp.get(code)
        if not ts:
            return False
        return datetime.utcnow() - ts < timedelta(minutes=max_age_minutes)

    ## @brief Documents get.
    ##
    def get(self, code: str):
        return self.data.get(code)

    ## @brief Documents set.
    ##
    def set(self, code: str, value: dict):
        self.data[code] = value
        self.timestamp[code] = datetime.utcnow()
