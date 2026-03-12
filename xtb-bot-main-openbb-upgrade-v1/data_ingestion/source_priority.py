SOURCE_PRIORITY = {
    "market_data": ["fmp", "yahoo"],
    "news": ["rss", "newsapi"],
    "macro": ["manual", "fred_proxy"],
}

def preferred_sources(kind: str):
    return SOURCE_PRIORITY.get(kind, [])
