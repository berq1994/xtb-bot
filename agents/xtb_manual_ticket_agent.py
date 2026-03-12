from __future__ import annotations

from integrations.openbb_engine import generate_market_overview, build_news_sentiment
from pathlib import Path


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
    sl, tp = _levels(price, "long" if direction == "long" else "short") if candidate else (0.0, 0.0)
    news_map = build_news_sentiment([symbol] if candidate else [])
    sentiment = news_map.get(symbol, {}).get("sentiment_label", "neutral") if candidate else "neutral"

    lines = []
    lines.append("XTB MANUAL TICKET")
    lines.append(f"Symbol: {symbol}")
    lines.append(f"Direction: {direction}")
    lines.append(f"Market regime: {overview.get('regime', 'mixed')}")
    lines.append(f"Entry reference: {price}")
    lines.append(f"Stop loss: {sl}")
    lines.append(f"Take profit: {tp}")
    lines.append(f"News sentiment: {sentiment}")
    lines.append("Checklist:")
    lines.append("- Confirm 15m and 1h chart structure")
    lines.append("- Confirm spread before entry")
    lines.append("- Max 1% account risk")
    lines.append("- Enter only on chart confirmation")

    Path("xtb_manual_ticket.txt").write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines)
