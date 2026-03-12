def fetch_market_snapshot(tickers):
    return [{"symbol": t, "price": None, "source": "placeholder"} for t in tickers]
