from __future__ import annotations

from integrations.openbb_engine import generate_market_overview, build_news_sentiment
from cz_utils import regime_cs, decision_cs, trend_cs, sentiment_cs


def run_supervisor(watchlist=None):
    overview = generate_market_overview(watchlist)
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])

    leader = leaders[0] if leaders else None
    laggard = laggards[0] if laggards else None

    symbols = []
    if leader:
        symbols.append(leader["symbol"])
    if laggard and laggard["symbol"] not in symbols:
        symbols.append(laggard["symbol"])

    news_map = build_news_sentiment(symbols)

    if overview.get("regime") == "risk_off":
        decision = "defensive_only"
        rationale = "Obchodovat menší velikostí nebo zůstat mimo trh – upřednostnit ochranu kapitálu."
    elif leader and leader.get("trend") == "up" and leader.get("change_pct", 0) > 0.4:
        leader_sentiment = news_map.get(leader["symbol"], {}).get("sentiment_label", "neutral")
        if leader_sentiment == "negative":
            decision = "wait"
            rationale = "Trend je sice pozitivní, ale zprávy zhoršují kvalitu setupu."
        else:
            decision = "watch_long"
            rationale = "Lead setup je silný a může nabídnout pokračování trendu."
    elif laggard and laggard.get("change_pct", 0) < -1.0:
        decision = "watch_hedge"
        rationale = "Slabý kandidát může fungovat jako hedge nebo short-watch."
    else:
        decision = "wait"
        rationale = "Není dostatečně kvalitní setup, vyčkat na potvrzení."

    lines = []
    lines.append("ROZHODNUTÍ SUPERVISORU")
    lines.append(f"Režim trhu: {regime_cs(overview.get('regime', 'mixed'))}")
    lines.append(f"Rozhodnutí: {decision_cs(decision)}")
    lines.append("")

    if leader:
        label = sentiment_cs(news_map.get(leader["symbol"], {}).get("sentiment_label", "neutral"))
        lines.append(
            f"Hlavní setup: {leader['symbol']} | {leader['change_pct']}% | trend {trend_cs(leader['trend'])} | zprávy {label}"
        )

    if laggard:
        label = sentiment_cs(news_map.get(laggard["symbol"], {}).get("sentiment_label", "neutral"))
        lines.append(
            f"Slabý setup: {laggard['symbol']} | {laggard['change_pct']}% | trend {trend_cs(laggard['trend'])} | zprávy {label}"
        )

    lines.append("")
    lines.append(f"Důvod: {rationale}")

    return "\n".join(lines)