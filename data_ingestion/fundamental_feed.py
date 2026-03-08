def fetch_fundamentals(tickers):
    return [{"symbol": t, "fundamental_score": None} for t in tickers]
