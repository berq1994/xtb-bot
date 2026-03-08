def fetch_news_bundle(tickers):
    return [{"symbol": t, "headlines": []} for t in tickers]
