def map_to_portfolio(events: list, tracked_symbols: list):
    tracked = set(tracked_symbols)
    mapped = []
    for event in events:
        hits = [t for t in event.get("tickers", []) if t in tracked]
        mapped.append({
            "event_id": event.get("event_id"),
            "headline": event.get("headline"),
            "kind": event.get("kind"),
            "impact": event.get("impact"),
            "relevance": event.get("relevance"),
            "portfolio_hits": hits,
            "portfolio_relevant": len(hits) > 0,
        })
    return mapped
