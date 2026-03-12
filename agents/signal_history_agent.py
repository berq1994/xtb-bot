from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from integrations.openbb_engine import generate_market_overview, build_news_sentiment
from cz_utils import decision_cs, regime_cs, sentiment_cs

HISTORY_PATH = Path("data/openbb_signal_history.jsonl")
JOURNAL_PATH = Path("data/openbb_trade_journal.txt")


def _levels(price: float, direction: str) -> tuple[float, float]:
    if direction == "long":
        return round(price * 0.985, 2), round(price * 1.03, 2)
    return round(price * 1.015, 2), round(price * 0.97, 2)


def build_snapshot_payload(watchlist=None) -> dict:
    overview = generate_market_overview(watchlist)
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])
    leader = leaders[0] if leaders else None
    laggard = laggards[0] if laggards else None

    symbols = [r["symbol"] for r in leaders + laggards]
    news_map = build_news_sentiment(symbols)

    leader_enriched = None
    if leader:
        leader_enriched = dict(leader)
        leader_enriched.update(news_map.get(leader["symbol"], {}))

    laggard_enriched = None
    if laggard:
        laggard_enriched = dict(laggard)
        laggard_enriched.update(news_map.get(laggard["symbol"], {}))

    if overview.get("regime") == "risk_off" and laggard:
        candidate = laggard
        direction = "short_watch"
    else:
        candidate = leader or laggard
        direction = "long" if candidate is leader else "short_watch"

    symbol = candidate["symbol"] if candidate else "NONE"
    price = float(candidate["price"]) if candidate else 0.0

    if candidate:
        sl, tp = _levels(price, "long" if direction == "long" else "short")
    else:
        sl, tp = 0.0, 0.0

    candidate_sentiment = news_map.get(symbol, {}) if candidate else {}

    if overview.get("regime") == "risk_off":
        decision = "defensive_only"
    elif (
        leader
        and leader.get("trend") == "up"
        and leader.get("change_pct", 0) > 0.4
        and news_map.get(leader["symbol"], {}).get("sentiment_label") != "negative"
    ):
        decision = "watch_long"
    elif laggard and laggard.get("change_pct", 0) < -1.0:
        decision = "watch_hedge"
    else:
        decision = "wait"

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "regime": overview.get("regime", "mixed"),
        "source": overview.get("source", "fallback"),
        "leader": leader_enriched,
        "laggard": laggard_enriched,
        "supervisor": {"decision": decision},
        "ticket": {
            "symbol": symbol,
            "direction": direction,
            "entry_reference": round(price, 2),
            "stop_loss": sl,
            "take_profit": tp,
            "news_sentiment": candidate_sentiment.get("sentiment_label", "neutral"),
        },
    }
    return payload


def append_history_entry(payload: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    leader_symbol = payload.get("leader", {}).get("symbol", "NONE") if payload.get("leader") else "NONE"
    ticket = payload.get("ticket", {})
    journal_lines = [
        f"[{payload['timestamp']}] režim={regime_cs(payload['regime'])} rozhodnutí={decision_cs(payload['supervisor']['decision'])}",
        f"lead={leader_symbol} ticket={ticket.get('symbol', 'NONE')} směr={ticket.get('direction', 'n/a')} vstup={ticket.get('entry_reference', 0)} sl={ticket.get('stop_loss', 0)} tp={ticket.get('take_profit', 0)} sentiment={sentiment_cs(ticket.get('news_sentiment', 'neutral'))}",
        "",
    ]
    with JOURNAL_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(journal_lines))


def run_log_signal(watchlist=None):
    payload = build_snapshot_payload(watchlist)
    append_history_entry(payload)

    lines = []
    lines.append("SIGNÁL ULOŽEN")
    lines.append(f"Čas: {payload['timestamp']}")
    lines.append(f"Režim: {regime_cs(payload['regime'])}")
    lines.append(f"Rozhodnutí: {decision_cs(payload['supervisor']['decision'])}")
    lines.append(f"Symbol ticketu: {payload['ticket']['symbol']}")
    lines.append(f"Soubor historie: {HISTORY_PATH}")
    lines.append(f"Soubor journalu: {JOURNAL_PATH}")

    return "\n".join(lines)