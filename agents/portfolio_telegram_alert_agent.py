from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agents.portfolio_context_agent import load_portfolio_symbols
from cz_utils import news_title_cs, sentiment_cs, source_cs, status_cs, trend_cs
from integrations.openbb_engine import build_news_sentiment, generate_market_overview
from production.telegram_http import send_telegram_http

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

TIMEZONE = os.getenv("TIMEZONE", "Europe/Prague")
STATE_PATH = Path(".state/delivery/portfolio_telegram_alert_state.json")
OUTPUT_PATH = Path("telegram_portfolio_alerts.txt")
ALERT_MOVE_MIN = float(os.getenv("PORTFOLIO_ALERT_MIN_MOVE", "2.4"))
ALERT_COOLDOWN_MIN = int(os.getenv("PORTFOLIO_ALERT_COOLDOWN_MIN", "180"))
ALERT_MAX_ITEMS = int(os.getenv("PORTFOLIO_ALERT_MAX_ITEMS", "5"))


def _now_local() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    try:
        return datetime.now(ZoneInfo(TIMEZONE))
    except Exception:
        return datetime.now()


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_state(payload: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _category(change_pct: float, sentiment: str, momentum_5d: float) -> str | None:
    if change_pct <= -3.0 and sentiment == "negative":
        return "obrana"
    if change_pct <= -ALERT_MOVE_MIN:
        return "silný_pokles"
    if change_pct >= 4.5 and momentum_5d >= 6.0:
        return "přehřátý_růst"
    if change_pct >= ALERT_MOVE_MIN and sentiment == "positive":
        return "silný_růst"
    if change_pct >= ALERT_MOVE_MIN:
        return "růst_bez_potvrzení"
    return None


def _hint(category: str) -> str:
    return {
        "obrana": "zkontrolovat zprávy, support a scénář omezení rizika",
        "silný_pokles": "ověřit, zda jde jen o korekci, nebo změnu investiční teze",
        "přehřátý_růst": "zvážit částečný výběr zisku nebo aspoň nehonit další vstup",
        "silný_růst": "sledovat pokračování, ale potvrdit graf a objem před jakýmkoli krokem",
        "růst_bez_potvrzení": "růst existuje, ale chybí jasné news potvrzení — nejednat impulzivně",
    }.get(category, "zkontrolovat graf a novou informaci")


def _fingerprint(symbol: str, category: str, change_pct: float, sentiment: str) -> str:
    bucket = int(math.floor(abs(change_pct) / 1.5))
    direction = "up" if change_pct >= 0 else "down"
    return f"{symbol}|{category}|{direction}|{bucket}|{sentiment}"


def _build_candidates() -> list[dict[str, Any]]:
    symbols = load_portfolio_symbols(limit=25)
    if not symbols:
        return []
    overview = generate_market_overview(symbols)
    rows = list(overview.get("symbols", []))
    news_map = build_news_sentiment(symbols[:10]) if symbols else {}
    source_label = source_cs(str(overview.get("source", rows[0].get("source", "unknown") if rows else "unknown")))

    candidates: list[dict[str, Any]] = []
    for row in rows:
        symbol = str(row.get("symbol", "")).upper().strip()
        if not symbol:
            continue
        change_pct = round(float(row.get("change_pct", 0.0)), 2)
        if abs(change_pct) < ALERT_MOVE_MIN:
            continue
        sentiment_payload = news_map.get(symbol, {})
        sentiment = str(sentiment_payload.get("sentiment_label", "neutral"))
        momentum_5d = round(float(row.get("momentum_5d", 0.0)), 2)
        category = _category(change_pct, sentiment, momentum_5d)
        if not category:
            continue
        headline = ""
        headlines = sentiment_payload.get("headlines") or []
        if headlines:
            headline = str(headlines[0]).strip()
        candidates.append(
            {
                "symbol": symbol,
                "price": round(float(row.get("price", 0.0)), 2),
                "change_pct": change_pct,
                "trend": str(row.get("trend", "flat")),
                "momentum_5d": momentum_5d,
                "sentiment": sentiment,
                "category": category,
                "headline": headline,
                "headline_cs": news_title_cs(headline),
                "source_label": source_label,
                "severity": round(abs(change_pct) + (1.0 if sentiment == "negative" else 0.6 if sentiment == "positive" else 0.0), 2),
            }
        )

    candidates.sort(key=lambda x: (x["severity"], abs(x["change_pct"])), reverse=True)
    return candidates


def build_portfolio_alert_message() -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    now_local = _now_local()
    state = _load_state()
    last_by_symbol = state.get("last_by_symbol", {}) if isinstance(state.get("last_by_symbol"), dict) else {}
    cooldown = timedelta(minutes=ALERT_COOLDOWN_MIN)

    selected: list[dict[str, Any]] = []
    new_state = {"last_by_symbol": dict(last_by_symbol)}

    for item in _build_candidates():
        symbol = item["symbol"]
        current_fp = _fingerprint(symbol, item["category"], float(item["change_pct"]), item["sentiment"])
        prev = last_by_symbol.get(symbol, {}) if isinstance(last_by_symbol.get(symbol), dict) else {}
        prev_fp = str(prev.get("fingerprint", ""))
        prev_sent_at = _parse_dt(prev.get("sent_at"))
        if prev_fp == current_fp and prev_sent_at and now_local - prev_sent_at < cooldown:
            continue
        selected.append(item)
        new_state["last_by_symbol"][symbol] = {
            "fingerprint": current_fp,
            "sent_at": now_local.isoformat(),
            "change_pct": item["change_pct"],
            "category": item["category"],
        }
        if len(selected) >= ALERT_MAX_ITEMS:
            break

    if not selected:
        return (
            "",
            [],
            {
                "generated_at": now_local.isoformat(),
                "reason": "NO_NEW_ACTIONABLE_ALERTS",
                "state": new_state,
            },
        )

    lines = []
    lines.append("PORTFOLIO ALERT – OKAMŽITÁ KONTROLA")
    lines.append(now_local.strftime("%d.%m.%Y %H:%M %Z"))
    lines.append("")
    for item in selected:
        headline = f" | zpráva: {item['headline_cs']}" if item.get("headline_cs") else ""
        lines.append(
            f"- {item['symbol']} {item['change_pct']}% | cena {item['price']} | trend {trend_cs(item['trend'])} | sentiment {sentiment_cs(item['sentiment'])} | zdroj cen {item['source_label']}"
        )
        lines.append(f"  Podnět: {_hint(item['category'])}{headline}")
    lines.append("")
    lines.append("Jen portfolio a jen nová situace — podobné alerty držím v cooldownu.")
    message = "\n".join(lines).strip()
    payload = {
        "generated_at": now_local.isoformat(),
        "selected": selected,
        "state": new_state,
    }
    return message, selected, payload


def run_portfolio_telegram_alerts(send: bool = True) -> str:
    message, selected, payload = build_portfolio_alert_message()
    state = payload.get("state", {}) if isinstance(payload, dict) else {}
    delivery = {"delivered": False, "reason": payload.get("reason", "NO_MESSAGE") if isinstance(payload, dict) else "NO_MESSAGE"}
    if message and send:
        delivery = send_telegram_http(message)
        if delivery.get("delivered"):
            _save_state(state)
    elif state:
        _save_state(state)

    preview = message or "Žádná nová akční situace v portfoliu."
    OUTPUT_PATH.write_text(preview, encoding="utf-8")
    report = [
        "TELEGRAM – PORTFOLIO ALERTY",
        f"Stav: {status_cs('sent' if delivery.get('delivered') else 'not_sent')}",
        f"Důvod: {delivery.get('reason', 'OK')}",
        f"Počet alertů: {len(selected)}",
        "",
        preview,
    ]
    return "\n".join(report)
