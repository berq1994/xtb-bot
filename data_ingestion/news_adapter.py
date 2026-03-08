from data_ingestion.universe_loader import load_enabled_universe

def fetch_news_bundle_final(limit: int = 10):
    universe = load_enabled_universe()[:limit]
    rows = []
    for item in universe:
        rows.append({
            "symbol": item["symbol"],
            "report": item["report"],
            "headlines": [],
            "source_used": "rss",
            "status": "adapter_ready",
        })
    return rows
