from live_intelligence.source_clients import (
    fetch_gdelt_geo,
    fetch_sec_corporate,
    fetch_earnings_calendar,
    fetch_macro_calendar,
)
from live_intelligence.scoring import relevance_score, impact_score
from live_intelligence.entity_router import route_entities

def build_unified_live_feed():
    raw = []
    raw.extend(fetch_gdelt_geo())
    raw.extend(fetch_sec_corporate())
    raw.extend(fetch_earnings_calendar())
    raw.extend(fetch_macro_calendar())

    rows = []
    for item in raw:
        rel = relevance_score(item["urgency"], item["source_quality"], item["market_link"])
        imp = impact_score(item["severity"], item["breadth"], item["duration"])
        routing = route_entities(item)
        rows.append({
            "kind": item["kind"],
            "source": item["source"],
            "headline": item["headline"],
            "summary_cz": item["summary_cz"],
            "tickers": routing["tickers"],
            "sectors": routing["sectors"],
            "relevance": rel,
            "impact": imp,
        })

    rows = sorted(rows, key=lambda x: (float(x["impact"]), float(x["relevance"])), reverse=True)
    return rows
