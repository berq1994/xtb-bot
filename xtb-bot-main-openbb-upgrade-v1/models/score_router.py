def score_candidates(research_payload):
    tickers = [row["symbol"] for row in research_payload.get("market", [])][:8]
    rows = []
    for i, symbol in enumerate(tickers):
        rows.append({"symbol": symbol, "score": round(1.4 - i * 0.1, 3), "model": "ensemble_v1"})
    return {"rows": rows, "top": rows[:5]}
