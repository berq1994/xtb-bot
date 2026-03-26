from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from integrations.openbb_engine import build_news_sentiment, generate_market_overview

HISTORY_PATH = Path("data/openbb_signal_history.jsonl")
RESEARCH_STATE_PATH = Path("data/research_live_state.json")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_research_state() -> dict:
    if not RESEARCH_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(RESEARCH_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _fallback_candidate_from_overview(overview: dict) -> dict:
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])
    if overview.get("regime") == "risk_off" and laggards:
        candidate = laggards[0]
        direction = "short_watch"
    elif leaders:
        candidate = leaders[0]
        direction = "long"
    elif laggards:
        candidate = laggards[0]
        direction = "short_watch"
    else:
        candidate = {}
        direction = "wait"
    return {"candidate": candidate, "direction": direction}


def _decision_from_candidate(regime: str, candidate: dict, sentiment_label: str) -> str:
    if not candidate:
        return "wait"
    if regime == "risk_off" and candidate.get("trend") == "down":
        return "watch_hedge"
    if sentiment_label == "negative" and candidate.get("trend") == "down":
        return "reduce_risk"
    if candidate.get("trend") == "up":
        return "watch_long"
    return "wait"


def build_snapshot_payload(
    overview_or_watchlist=None,
    decision: str | None = None,
    ticket_symbol: str | None = None,
) -> dict:
    state = overview_or_watchlist if isinstance(overview_or_watchlist, dict) else _load_research_state()

    top_items = state.get("top_items", []) if isinstance(state, dict) else []
    if top_items:
        top = top_items[0]
        regime = str(state.get("regime", "mixed"))
        source = str(state.get("source", "unknown"))
        symbol = str(ticket_symbol or top.get("symbol") or "")
        entry_price = float(top.get("price", 0.0) or 0.0)
        direction = "short_watch" if regime == "risk_off" and str(top.get("trend", "flat")) == "down" else "long"
        sentiment_label = str(top.get("sentiment_label", "neutral"))
        inferred_decision = decision or _decision_from_candidate(regime, top, sentiment_label)
        return {
            "signal_id": f"{_utc_now_iso()}|{symbol}",
            "timestamp": _utc_now_iso(),
            "regime": regime,
            "decision": inferred_decision,
            "ticket_symbol": symbol or None,
            "entry_price": round(entry_price, 2) if entry_price else None,
            "source": source,
            "leaders": top_items[:3],
            "laggards": [],
            "ticket": {
                "symbol": symbol,
                "direction": direction,
                "entry_reference": round(entry_price, 2) if entry_price else None,
                "priority_score": top.get("priority_score"),
                "category": top.get("category"),
            },
            "supervisor": {
                "decision": inferred_decision,
                "reason": top.get("category"),
            },
            "features": {
                "trend": top.get("trend"),
                "change_pct": top.get("change_pct"),
                "momentum_5d": top.get("momentum_5d"),
                "momentum_20d": top.get("momentum_20d"),
                "sentiment_label": sentiment_label,
                "sentiment_score": top.get("sentiment_score"),
                "theme_overlap_penalty": top.get("theme_overlap_penalty"),
                "held": top.get("held"),
                "pnl_vs_cost_pct": top.get("pnl_vs_cost_pct"),
                "news_count": top.get("news_count"),
                "catalysts": top.get("catalysts", []),
                "data_source": source,
                "news_sources": top.get("trusted_sources", []),
                "news_providers": top.get("news_providers", []),
                "evidence_score": top.get("evidence_score"),
                "evidence_grade": top.get("evidence_grade"),
                "playbooks": top.get("playbooks", []),
                "study_alignment_score": top.get("study_alignment_score"),
                "matched_studies": top.get("matched_studies", []),
            },
        }

    if isinstance(overview_or_watchlist, dict):
        overview = overview_or_watchlist
    else:
        overview = generate_market_overview(overview_or_watchlist)

    choice = _fallback_candidate_from_overview(overview)
    candidate = choice["candidate"]
    symbol = str(ticket_symbol or candidate.get("symbol") or "")
    news_map = build_news_sentiment([symbol] if symbol else [])
    sentiment_label = news_map.get(symbol, {}).get("sentiment_label", "neutral") if symbol else "neutral"
    inferred_decision = decision or _decision_from_candidate(str(overview.get("regime", "mixed")), candidate, sentiment_label)

    return {
        "signal_id": f"{_utc_now_iso()}|{symbol}",
        "timestamp": _utc_now_iso(),
        "regime": overview.get("regime", "mixed"),
        "decision": inferred_decision,
        "ticket_symbol": symbol or None,
        "entry_price": candidate.get("price"),
        "source": overview.get("source", "unknown"),
        "leaders": overview.get("leaders", [])[:3],
        "laggards": overview.get("laggards", [])[:3],
        "ticket": {
            "symbol": symbol,
            "direction": choice["direction"],
            "entry_reference": candidate.get("price"),
        },
        "supervisor": {
            "decision": inferred_decision,
            "reason": f"trend={candidate.get('trend', 'flat')} sentiment={sentiment_label}",
        },
        "features": {
            "trend": candidate.get("trend"),
            "change_pct": candidate.get("change_pct"),
            "momentum_5d": candidate.get("momentum_5d"),
            "momentum_20d": candidate.get("momentum_20d"),
            "sentiment_label": sentiment_label,
            "sentiment_score": news_map.get(symbol, {}).get("sentiment_score", 0),
            "theme_overlap_penalty": 0.0,
            "held": False,
            "pnl_vs_cost_pct": None,
            "news_count": news_map.get(symbol, {}).get("news_count", 0),
            "catalysts": news_map.get(symbol, {}).get("catalysts", []),
            "data_source": overview.get("source", "unknown"),
            "news_sources": [],
            "news_providers": [],
            "evidence_score": None,
            "evidence_grade": None,
            "playbooks": [],
            "study_alignment_score": None,
            "matched_studies": [],
        },
    }


def append_history_entry(payload: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run_log_signal(
    overview_or_watchlist=None,
    decision: str | None = None,
    ticket_symbol: str | None = None,
) -> str:
    payload = build_snapshot_payload(overview_or_watchlist, decision, ticket_symbol)
    append_history_entry(payload)

    lines = []
    lines.append("SIGNÁL ULOŽEN")
    lines.append(f"Čas: {payload['timestamp']}")
    lines.append(f"Režim: {payload['regime']}")
    lines.append(f"Rozhodnutí: {payload['decision']}")
    lines.append(f"Ticker: {payload['ticket_symbol'] or '-'}")
    lines.append(f"Entry reference: {payload.get('entry_price') or '-'}")
    lines.append(f"Soubor historie: {HISTORY_PATH}")
    return "\n".join(lines)


def run_signal_history_review(limit: int = 10) -> str:
    if not HISTORY_PATH.exists():
        return "PŘEHLED HISTORIE SIGNÁLŮ\nŽádná historie zatím neexistuje."

    rows = []
    with HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    rows = rows[-limit:]
    lines = []
    lines.append("PŘEHLED HISTORIE SIGNÁLŮ")
    lines.append(f"Počet záznamů: {len(rows)}")
    lines.append("")

    if not rows:
        lines.append("Žádná validní data.")
        return "\n".join(lines)

    for row in rows:
        ts = row.get("timestamp", "neznámý čas")
        regime = row.get("regime", "unknown")
        decision = row.get("decision", "unknown")
        ticket = row.get("ticket_symbol") or row.get("ticket", {}).get("symbol") or "-"
        entry = row.get("entry_price") or row.get("ticket", {}).get("entry_reference") or "-"
        lines.append(f"- {ts} | režim {regime} | rozhodnutí {decision} | ticker {ticket} | entry {entry}")

    return "\n".join(lines)
