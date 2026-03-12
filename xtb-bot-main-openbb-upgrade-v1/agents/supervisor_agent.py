from __future__ import annotations

from integrations.openbb_engine import generate_market_overview, build_news_sentiment


def _decision_from_signal(regime: str, leader: dict | None, laggard: dict | None, news_map: dict) -> str:
    if regime == "risk_off":
        return "defensive_only"
    if not leader:
        return "no_trade"
    leader_news = news_map.get(leader["symbol"], {})
    sentiment = leader_news.get("sentiment_label", "neutral")
    if leader.get("trend") == "up" and leader.get("change_pct", 0) > 0.4 and sentiment != "negative":
        return "watch_long"
    if laggard and laggard.get("change_pct", 0) < -1.0:
        return "watch_hedge"
    return "wait"


def run_supervisor(watchlist=None):
    overview = generate_market_overview(watchlist)
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])
    leader = leaders[0] if leaders else None
    laggard = laggards[0] if laggards else None
    symbols = [r["symbol"] for r in leaders + laggards]
    news_map = build_news_sentiment(symbols)
    decision = _decision_from_signal(overview.get("regime", "mixed"), leader, laggard, news_map)

    lines = []
    lines.append("SUPERVISOR DECISION")
    lines.append(f"Market regime: {overview.get('regime', 'mixed')}")
    lines.append(f"Decision: {decision}")
    if leader:
        ls = news_map.get(leader['symbol'], {})
        lines.append(f"Lead setup: {leader['symbol']} | {leader['change_pct']}% | trend {leader['trend']} | news {ls.get('sentiment_label', 'neutral')}")
    if laggard:
        ws = news_map.get(laggard['symbol'], {})
        lines.append(f"Weak setup: {laggard['symbol']} | {laggard['change_pct']}% | trend {laggard['trend']} | news {ws.get('sentiment_label', 'neutral')}")
    lines.append("Next step:")
    if decision == "watch_long":
        lines.append("- Open XTB chart")
        lines.append("- Wait for breakout confirmation")
        lines.append("- Use manual ticket and max 1% risk")
    elif decision == "watch_hedge":
        lines.append("- Avoid impulsive long entries")
        lines.append("- Consider defensive hedge review")
    elif decision == "defensive_only":
        lines.append("- Trade small or stay flat")
        lines.append("- Prioritize capital protection")
    else:
        lines.append("- Wait for cleaner confirmation")
    return "\n".join(lines)
