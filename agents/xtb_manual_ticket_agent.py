from __future__ import annotations

from pathlib import Path

from integrations.openbb_engine import generate_market_overview, build_news_sentiment
from cz_utils import regime_cs, sentiment_cs, direction_cs


def _levels(price: float, direction: str) -> tuple[float, float]:
    if direction == "long":
        sl = round(price * 0.985, 2)
        tp = round(price * 1.03, 2)
    else:
        sl = round(price * 1.015, 2)
        tp = round(price * 0.97, 2)
    return sl, tp


def run_xtb_manual_ticket(watchlist=None):
    overview = generate_market_overview(watchlist)
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])

    leader = leaders[0] if leaders else None
    laggard = laggards[0] if laggards else None

    candidate = leader if overview.get("regime") != "risk_off" and leader else laggard
    direction = "long" if candidate is leader else "short_watch"

    symbol = candidate["symbol"] if candidate else "NONE"
    price = float(candidate["price"]) if candidate else 0.0

    if candidate:
        sl, tp = _levels(price, "long" if direction == "long" else "short")
    else:
        sl, tp = 0.0, 0.0

    news_map = build_news_sentiment([symbol] if candidate else [])
    sentiment = news_map.get(symbol, {}).get("sentiment_label", "neutral") if candidate else "neutral"

    lines = []
    lines.append("RUÄŚNĂŤ XTB TICKET")
    lines.append(f"Symbol: {symbol}")
    lines.append(f"SmÄ›r: {direction_cs(direction)}")
    lines.append(f"ReĹľim trhu: {regime_cs(overview.get('regime', 'mixed'))}")
    lines.append(f"VstupnĂ­ reference: {price}")
    lines.append(f"Stop loss: {sl}")
    lines.append(f"Take profit: {tp}")
    lines.append(f"Sentiment zprĂˇv: {sentiment_cs(sentiment)}")
    lines.append("KontrolnĂ­ seznam:")
    lines.append("- Potvrdit strukturu na 15m a 1h grafu")
    lines.append("- Potvrdit spread pĹ™ed vstupem")
    lines.append("- Max. riziko ĂşÄŤtu 1 %")
    lines.append("- Vstoupit jen po potvrzenĂ­ v grafu")

    output = "
".join(lines)
    Path("xtb_manual_ticket.txt").write_text(output, encoding="utf-8")
    return output

