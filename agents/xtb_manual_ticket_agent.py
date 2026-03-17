from __future__ import annotations

from pathlib import Path
from typing import List

from integrations.openbb_engine import generate_market_overview, build_news_sentiment
from cz_utils import regime_cs, sentiment_cs, direction_cs

try:
    from production.fmp_market_data import fetch_eod_series
except Exception:  # pragma: no cover
    fetch_eod_series = None


def _avg_abs_move_pct(closes: List[float]) -> float:
    if len(closes) < 2:
        return 1.2
    moves = []
    for prev, cur in zip(closes[:-1], closes[1:]):
        if prev:
            moves.append(abs((cur - prev) / prev) * 100)
    return round(sum(moves) / len(moves), 2) if moves else 1.2


def _levels(price: float, direction: str, closes: List[float]) -> tuple[float, float, float]:
    vol_pct = max(_avg_abs_move_pct(closes), 0.8)
    risk_pct = max(vol_pct * 0.9, 1.0)
    reward_pct = max(risk_pct * 1.8, 2.0)
    if direction == "long":
        sl = round(price * (1 - risk_pct / 100), 2)
        tp = round(price * (1 + reward_pct / 100), 2)
    else:
        sl = round(price * (1 + risk_pct / 100), 2)
        tp = round(price * (1 - reward_pct / 100), 2)
    return sl, tp, risk_pct


def run_xtb_manual_ticket(watchlist=None):
    overview = generate_market_overview(watchlist)
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])

    leader = leaders[0] if leaders else None
    laggard = laggards[0] if laggards else None

    candidate = leader if overview.get("regime") != "risk_off" and leader else laggard
    direction = "long" if candidate is leader and leader else "short_watch"

    symbol = candidate["symbol"] if candidate else "NONE"
    price = float(candidate["price"]) if candidate else 0.0

    closes: List[float] = list(candidate.get("closes", [])) if candidate else []
    if not closes and candidate and fetch_eod_series is not None:
        try:
            closes = [float(r["close"]) for r in fetch_eod_series(symbol, days_back=12)]
        except Exception:
            closes = []

    if candidate:
        sl, tp, risk_pct = _levels(price, "long" if direction == "long" else "short", closes)
    else:
        sl, tp, risk_pct = 0.0, 0.0, 0.0

    news_map = build_news_sentiment([symbol] if candidate else [])
    sentiment = news_map.get(symbol, {}).get("sentiment_label", "neutral") if candidate else "neutral"

    lines = []
    lines.append("RUČNÍ XTB TICKET")
    lines.append(f"Symbol: {symbol}")
    lines.append(f"Směr: {direction_cs(direction)}")
    lines.append(f"Režim trhu: {regime_cs(overview.get('regime', 'mixed'))}")
    lines.append(f"Zdroj dat: {overview.get('source', 'unknown')}")
    lines.append(f"Vstupní reference: {price}")
    lines.append(f"Stop loss: {sl}")
    lines.append(f"Take profit: {tp}")
    lines.append(f"Odhad volatility: {risk_pct}%")
    lines.append(f"Sentiment zpráv: {sentiment_cs(sentiment)}")
    lines.append("Kontrolní seznam:")
    lines.append("- Potvrdit strukturu na 15m a 1h grafu")
    lines.append("- Potvrdit spread před vstupem")
    lines.append("- Max. riziko účtu 1 %")
    lines.append("- Vstoupit jen po potvrzení v grafu")

    output = "\n".join(lines)
    Path("xtb_manual_ticket.txt").write_text(output, encoding="utf-8")
    return output
