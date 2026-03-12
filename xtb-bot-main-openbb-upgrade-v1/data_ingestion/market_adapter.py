from data_ingestion.universe_loader import load_enabled_universe
from data_ingestion.source_router import route_symbol

def fetch_market_bundle(limit: int = 10):
    universe = load_enabled_universe()[:limit]
    rows = []
    for item in universe:
        routing = route_symbol(item["symbol"], "market_data")
        rows.append({
            "symbol": item["symbol"],
            "report": item["report"],
            "sector": item["sector"],
            "routing": routing,
            "source_used": routing["preferred_sources"][0] if routing["preferred_sources"] else "unknown",
            "price": None,
            "volume": None,
            "status": "adapter_ready",
        })
    return rows
