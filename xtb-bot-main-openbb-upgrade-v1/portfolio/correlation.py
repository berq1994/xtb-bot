def correlation_penalty(symbol: str, open_positions: list) -> float:
    semis = {"NVDA", "AMD", "SMH"}
    mega = {"AAPL", "MSFT", "META", "GOOGL", "AMZN", "QQQ", "SPY"}
    same_bucket = 0
    for p in open_positions:
        s = str(p.get("symbol", "")).upper()
        if symbol in semis and s in semis:
            same_bucket += 1
        if symbol in mega and s in mega:
            same_bucket += 1
    return 0.7 if same_bucket >= 1 else 1.0
