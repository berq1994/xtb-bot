def build_portfolio(signal_payload):
    portfolio = []
    for row in signal_payload.get("top", [])[:5]:
        portfolio.append({
            "symbol": row["symbol"],
            "target_weight_pct": 5.0,
            "score": row["score"],
        })
    return portfolio
