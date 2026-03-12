from data_ingestion.universe_loader import load_enabled_universe

def fetch_fundamental_bundle(limit: int = 10):
    universe = load_enabled_universe()[:limit]
    rows = []
    for item in universe:
        rows.append({
            "symbol": item["symbol"],
            "report": item["report"],
            "fundamental_score": None,
            "source_used": "fmp",
            "status": "adapter_ready",
        })
    return rows
