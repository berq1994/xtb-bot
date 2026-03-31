from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

STATE_PATH = Path("data/macro_calendar_state.json")
CACHE_PATH = Path("data/macro_calendar_cache.json")
REPORT_PATH = Path("macro_calendar_report.txt")
CACHE_TTL_SECONDS = 60 * 60 * 12
TIMEOUT = 5
MAX_EVENTS = 8


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_cache(payload: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fmp_calendar(start: date, end: date) -> list[dict[str, Any]]:
    api_key = str(os.getenv("FMP_API_KEY") or os.getenv("FMPAPIKEY") or "").strip()
    if not api_key:
        return []
    url = "https://financialmodelingprep.com/stable/economic-calendar"
    try:
        response = requests.get(
            url,
            params={"from": start.isoformat(), "to": end.isoformat(), "apikey": api_key},
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; XTBResearchBot/1.0)"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _fallback_events(start: date) -> list[dict[str, Any]]:
    return [
        {"date": start.isoformat(), "country": "US", "event": "Kontrola makro kalendáře: inflace / CPI", "importance": "high"},
        {"date": (start + timedelta(days=1)).isoformat(), "country": "US", "event": "Kontrola centrálních bank / sazby", "importance": "high"},
        {"date": (start + timedelta(days=2)).isoformat(), "country": "US", "event": "Kontrola trhu práce / nezaměstnanost", "importance": "medium"},
    ]


def load_macro_calendar(days: int = 7) -> dict[str, Any]:
    cache = _load_cache()
    now = time.time()
    if cache.get("expires_at", 0) > now and isinstance(cache.get("data"), dict):
        return cache["data"]
    start = date.today()
    end = start + timedelta(days=max(3, days))
    rows = _fmp_calendar(start, end)
    if not rows:
        rows = _fallback_events(start)
        source = "fallback"
    else:
        source = "fmp_calendar"
    normalized = []
    for row in rows[:MAX_EVENTS]:
        event = str(row.get("event") or row.get("title") or row.get("name") or "").strip()
        if not event:
            continue
        importance = str(row.get("importance") or row.get("impact") or "medium").lower()
        country = str(row.get("country") or row.get("currency") or "US")
        normalized.append({
            "date": str(row.get("date") or row.get("eventDate") or ""),
            "country": country,
            "event": event,
            "importance": importance,
        })
    macro_risk = "low"
    if any(str(i.get("importance")) in {"high", "3", "4"} for i in normalized):
        macro_risk = "high"
    elif any(str(i.get("importance")) in {"medium", "2"} for i in normalized):
        macro_risk = "medium"
    payload = {"source": source, "events": normalized, "macro_risk": macro_risk, "window_days": days}
    cache = {"expires_at": now + CACHE_TTL_SECONDS, "data": payload}
    _save_cache(cache)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_macro_calendar(days: int = 7) -> str:
    payload = load_macro_calendar(days)
    lines = ["MAKRO KALENDÁŘ", f"Zdroj: {payload.get('source')}", f"Makro riziko: {payload.get('macro_risk')}"]
    events = payload.get("events", []) if isinstance(payload.get("events"), list) else []
    for row in events[:5]:
        lines.append(f"- {row.get('date')} | {row.get('country')} | {row.get('event')} | importance {row.get('importance')}")
    if len(lines) <= 3:
        lines.append("- Bez nových makro událostí.")
    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    return report
