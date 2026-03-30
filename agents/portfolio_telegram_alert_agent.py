
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
RESEARCH_STATE_PATH = Path("data/research_live_state.json")
ALERT_MOVE_MIN = float(os.getenv("PORTFOLIO_ALERT_MIN_MOVE", "2.6"))
ALERT_COOLDOWN_MIN = int(os.getenv("PORTFOLIO_ALERT_COOLDOWN_MIN", "180"))
ALERT_MAX_ITEMS = int(os.getenv("PORTFOLIO_ALERT_MAX_ITEMS", "3"))
ALERT_MIN_ACTIONABILITY = float(os.getenv("PORTFOLIO_ALERT_MIN_ACTIONABILITY", "4.4"))
ALERT_WINDOW_START_HOUR = int(os.getenv("ALERT_WINDOW_START_HOUR", "8"))
ALERT_WINDOW_END_HOUR = int(os.getenv("ALERT_WINDOW_END_HOUR", "21"))
DAILY_MAX_PER_SYMBOL = int(os.getenv("PORTFOLIO_ALERT_DAILY_MAX_PER_SYMBOL", "2"))


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


def _load_research_state() -> dict[str, Any]:
    if not RESEARCH_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(RESEARCH_STATE_PATH.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _is_within_alert_window(now_local: datetime) -> bool:
    if ALERT_WINDOW_START_HOUR <= now_local.hour < ALERT_WINDOW_END_HOUR:
        return True
    if now_local.hour == ALERT_WINDOW_END_HOUR and now_local.minute == 0:
        return True
    return False


def _fingerprint(symbol: str, bucket: str, change_pct: float, sentiment: str, headline: str) -> str:
    move_bucket = int(math.floor(abs(change_pct) / 1.25))
    direction = "up" if change_pct >= 0 else "down"
    headline_key = news_title_cs(headline)[:48].lower() if headline else ''
    return f"{symbol}|{bucket}|{direction}|{move_bucket}|{sentiment}|{headline_key}"


def _build_candidates() -> list[dict[str, Any]]:
    symbols = load_portfolio_symbols(limit=25)
    if not symbols:
        return []
    overview = generate_market_overview(symbols)
    rows = list(overview.get('symbols', []))
    news_map = build_news_sentiment(symbols[:10]) if symbols else {}
    source_label = source_cs(str(overview.get('source', rows[0].get('source', 'unknown') if rows else 'unknown')))

    research_state = _load_research_state()
    queue = research_state.get('action_queue', []) if isinstance(research_state, dict) else []
    queue_map = {str(item.get('symbol', '')).upper().strip(): item for item in queue if str(item.get('symbol', '')).strip()}

    candidates: list[dict[str, Any]] = []
    for row in rows:
        symbol = str(row.get('symbol', '')).upper().strip()
        if not symbol:
            continue
        quality = queue_map.get(symbol, {}) if isinstance(queue_map.get(symbol, {}), dict) else {}
        actionability_score = float(quality.get('actionability_score', 0.0) or 0.0)
        if float(quality.get('data_quality_score', 0.7) or 0.7) < 0.6:
            continue
        if str(quality.get('delivery_channel', 'none')) != 'telegram':
            continue
        if actionability_score < ALERT_MIN_ACTIONABILITY:
            continue
        change_pct = round(float(row.get('change_pct', 0.0)), 2)
        if abs(change_pct) < ALERT_MOVE_MIN and actionability_score < (ALERT_MIN_ACTIONABILITY + 0.4):
            continue
        sentiment_payload = news_map.get(symbol, {})
        sentiment = str(quality.get('sentiment_label') or sentiment_payload.get('sentiment_label', 'neutral'))
        headlines = sentiment_payload.get('headlines') or quality.get('headlines') or []
        headline = str(headlines[0]).strip() if headlines else ''
        candidates.append(
            {
                'symbol': symbol,
                'price': round(float(row.get('price', 0.0)), 2),
                'change_pct': change_pct,
                'trend': str(quality.get('trend') or row.get('trend', 'flat')),
                'momentum_5d': round(float(quality.get('momentum_5d') or row.get('momentum_5d', 0.0)), 2),
                'sentiment': sentiment,
                'category': str(quality.get('category', 'watchlist_monitor') or 'watchlist_monitor'),
                'headline': headline,
                'headline_cs': news_title_cs(headline),
                'source_label': source_label,
                'severity': round(abs(change_pct) + max(actionability_score - 3.2, 0.0), 2),
                'actionability_score': round(actionability_score, 2),
                'action_bucket': str(quality.get('action_bucket', 'medium') or 'medium'),
                'urgency_label': str(quality.get('urgency_label', 'mít na očích') or 'mít na očích'),
                'action_hint': str(quality.get('action_hint') or ''),
            }
        )

    candidates.sort(key=lambda x: (x['actionability_score'], x['severity'], abs(x['change_pct'])), reverse=True)
    return candidates


def build_portfolio_alert_message() -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    now_local = _now_local()
    state = _load_state()
    last_by_symbol = state.get("last_by_symbol", {}) if isinstance(state.get("last_by_symbol"), dict) else {}
    daily_counter = state.get('daily_counter', {}) if isinstance(state.get('daily_counter'), dict) else {}
    day_key = now_local.strftime('%Y-%m-%d')
    cooldown = timedelta(minutes=ALERT_COOLDOWN_MIN)

    selected: list[dict[str, Any]] = []
    new_state = {"last_by_symbol": dict(last_by_symbol), 'daily_counter': dict(daily_counter)}

    for item in _build_candidates():
        symbol = item["symbol"]
        current_fp = _fingerprint(symbol, item["action_bucket"], float(item["change_pct"]), item["sentiment"], item.get('headline', ''))
        prev = last_by_symbol.get(symbol, {}) if isinstance(last_by_symbol.get(symbol), dict) else {}
        prev_fp = str(prev.get("fingerprint", ""))
        prev_sent_at = _parse_dt(prev.get("sent_at"))
        if prev_fp == current_fp and prev_sent_at and now_local - prev_sent_at < cooldown:
            continue
        symbol_day_count = int((daily_counter.get(day_key, {}) or {}).get(symbol, 0) or 0)
        if symbol_day_count >= DAILY_MAX_PER_SYMBOL:
            continue
        selected.append(item)
        new_state["last_by_symbol"][symbol] = {
            "fingerprint": current_fp,
            "sent_at": now_local.isoformat(),
            "change_pct": item["change_pct"],
            "bucket": item["action_bucket"],
        }
        new_state.setdefault('daily_counter', {}).setdefault(day_key, {})[symbol] = symbol_day_count + 1
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
            f"- {item['symbol']} {item['change_pct']}% | cena {item['price']} | trend {trend_cs(item['trend'])} | sentiment {sentiment_cs(item['sentiment'])} | akčnost {item.get('actionability_score', 0.0)} | {item.get('urgency_label')} | zdroj cen {item['source_label']}"
        )
        lines.append(f"  Podnět: {item.get('action_hint')}{headline}")
    lines.append("")
    lines.append("Jen portfolio, jen nová situace a přísnější anti-spam filtr.")
    message = "\n".join(lines).strip()
    payload = {"generated_at": now_local.isoformat(), "selected": selected, "state": new_state}
    return message, selected, payload


def run_portfolio_telegram_alerts(send: bool = True) -> str:
    now_local = _now_local()
    window_label = f"{ALERT_WINDOW_START_HOUR:02d}:00-{ALERT_WINDOW_END_HOUR:02d}:00"
    if send and not _is_within_alert_window(now_local):
        preview = f"Mimo časové okno alertů ({window_label}). Telegram neposlán."
        OUTPUT_PATH.write_text(preview, encoding="utf-8")
        report = ["TELEGRAM – PORTFOLIO ALERTY", f"Stav: {status_cs('not_sent')}", "Důvod: OUTSIDE_ALERT_WINDOW", f"Časové okno: {window_label}", "", preview]
        return "\n".join(report)

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
        f"Časové okno: {window_label}",
        f"Počet alertů: {len(selected)}",
        "",
        preview,
    ]
    return "\n".join(report)
