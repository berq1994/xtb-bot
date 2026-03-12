from __future__ import annotations

from integrations.openbb_engine import generate_market_overview, build_news_sentiment
from cz_utils import regime_cs, trend_cs, sentiment_cs, decision_cs


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
    lines.append("ROZHODNUTÍ SUPERVISORU")
    lines.append(f"Režim trhu: {regime_cs(overview.get('regime', 'mixed'))}")
    lines.append(f"Rozhodnutí: {decision_cs(decision)}")

    if leader:
        ls = news_map.get(leader["symbol"], {})
        lines.append(
            f"Hlavní setup: {leader['symbol']} | {leader['change_pct']}% | trend {trend_cs(leader['trend'])} | zprávy {sentiment_cs(ls.get('sentiment_label', 'neutral'))}"
        )

    if laggard:
        ws = news_map.get(laggard["symbol"], {})
        lines.append(
            f"Slabý setup: {laggard['symbol']} | {laggard['change_pct']}% | trend {trend_cs(laggard['trend'])} | zprávy {sentiment_cs(ws.get('sentiment_label', 'neutral'))}"
        )

    lines.append("Další krok:")
    if decision == "watch_long":
        lines.append("- Otevřít graf v XTB")
        lines.append("- Počkat na potvrzení breakoutu")
        lines.append("- Použít ruční ticket a max. riziko 1 %")
    elif decision == "watch_hedge":
        lines.append("- Neotvírat impulzivní long")
        lines.append("- Zvážit defenzivní hedge")
    elif decision == "defensive_only":
        lines.append("- Obchodovat menší velikostí nebo zůstat mimo trh")
        lines.append("- Upřednostnit ochranu kapitálu")
    else:
        lines.append("- Vyčkat na čistší potvrzení")

    return "\\n".join(lines)