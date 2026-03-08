def route_entities(item: dict):
    tickers = item.get("tickers", [])
    sectors = []
    for t in tickers:
        if t in ["NVDA", "AMD", "TSM", "MSFT"]:
            sectors.append("Technology")
        elif t in ["OIL", "XOM", "CVX"]:
            sectors.append("Energy")
        elif t in ["BTC"]:
            sectors.append("Crypto")
    return {
        "tickers": tickers,
        "sectors": sorted(set(sectors)),
    }
