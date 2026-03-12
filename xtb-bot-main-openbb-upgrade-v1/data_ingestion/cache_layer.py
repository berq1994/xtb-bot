from data_quality.cache_manager import cache_put, cache_get

def save_market_cache(symbol: str, payload: dict):
    cache_put(f"market_{symbol}", payload)

def load_market_cache(symbol: str):
    return cache_get(f"market_{symbol}")
