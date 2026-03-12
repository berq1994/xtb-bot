from data_ingestion.source_priority import preferred_sources
from data_quality.source_resolver import resolve_symbol

def route_symbol(symbol: str, kind: str = "market_data"):
    sources = preferred_sources(kind)
    return {
        "symbol": symbol,
        "preferred_sources": sources,
        "resolved": {
            source: resolve_symbol(symbol, source if source in ["yahoo", "fmp"] else "yahoo")
            for source in sources
        }
    }
