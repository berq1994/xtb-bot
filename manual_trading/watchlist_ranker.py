def rank_watchlist(top_signals: list):
    ordered = sorted(top_signals, key=lambda x: float(x.get("score", 0)), reverse=True)
    rows = []
    for idx, row in enumerate(ordered, start=1):
        rows.append({
            "rank": idx,
            "symbol": row.get("symbol"),
            "score": row.get("score"),
        })
    return rows
