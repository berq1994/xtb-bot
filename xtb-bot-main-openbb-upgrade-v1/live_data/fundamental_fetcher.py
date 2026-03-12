from data_ingestion.universe_loader import load_enabled_universe
from live_data.failover_router import choose_provider
from live_data.source_health import mark_success

def fetch_fundamentals_live(limit: int = 10):
    provider = choose_provider("fmp", ["yahoo"])
    rows = []
    for item in load_enabled_universe()[:limit]:
        rows.append({
            "symbol": item["symbol"],
            "provider": provider,
            "fundamental_score": None,
            "status": "live_fetch_ready",
        })
    mark_success(provider)
    return {"provider_used": provider, "rows": rows}
