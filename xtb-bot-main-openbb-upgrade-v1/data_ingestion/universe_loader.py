from data_quality.ticker_registry import load_ticker_registry

def load_enabled_universe():
    reg = load_ticker_registry()
    out = []
    for symbol, rec in reg.items():
        if bool(rec.get("enabled", False)):
            out.append({
                "symbol": symbol,
                "report": rec.get("report", symbol),
                "sector": rec.get("sector", "Unknown"),
                "yahoo": rec.get("yahoo", symbol),
                "fmp": rec.get("fmp", symbol),
            })
    return out
