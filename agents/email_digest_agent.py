from __future__ import annotations

import json
import os
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

import requests

from agents.portfolio_context_agent import load_portfolio_symbols
from integrations.openbb_engine import build_news_sentiment, generate_market_overview
from real_delivery.email_live import send_email_live

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

TIMEZONE = os.getenv("TIMEZONE", "Europe/Prague")
OUTPUT_PATH = Path("daily_digest_email.txt")
STATE_PATH = Path(".state/delivery/email_digest_state.json")
REQUEST_TIMEOUT = 5


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


def _normalize_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _fetch_google_news(query: str, limit: int = 4) -> list[dict[str, str]]:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; XTBResearchBot/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        raw = response.text
    except Exception:
        return []

    try:
        root = ET.fromstring(raw)
    except Exception:
        return []

    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in root.findall(".//item"):
        title = _normalize_text(item.findtext("title") or "")
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        source = "Google News"
        source_node = item.find("source")
        if source_node is not None and (source_node.text or "").strip():
            source = _normalize_text(source_node.text or "")
        items.append(
            {
                "title": title,
                "source": source,
                "published": _normalize_text(item.findtext("pubDate") or ""),
                "summary": _normalize_text(item.findtext("description") or ""),
            }
        )
        if len(items) >= limit:
            break
    return items


def _portfolio_rows() -> list[dict[str, Any]]:
    symbols = load_portfolio_symbols(limit=25)
    overview = generate_market_overview(symbols)
    return list(overview.get("symbols", []))


def _portfolio_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "regime": "mixed",
            "source": "unknown",
            "avg_change": 0.0,
            "leaders": [],
            "laggards": [],
            "movers": [],
        }
    leaders = sorted(rows, key=lambda x: float(x.get("change_pct", 0.0)), reverse=True)[:3]
    laggards = sorted(rows, key=lambda x: float(x.get("change_pct", 0.0)))[:3]
    movers = sorted(rows, key=lambda x: abs(float(x.get("change_pct", 0.0))), reverse=True)[:5]
    avg_change = round(sum(float(r.get("change_pct", 0.0)) for r in rows) / len(rows), 2)
    source = str(rows[0].get("source", "unknown"))
    proxy_overview = generate_market_overview(["SPY", "QQQ", "BTC-USD", "TLT"])
    return {
        "regime": proxy_overview.get("regime", "mixed"),
        "source": source,
        "avg_change": avg_change,
        "leaders": leaders,
        "laggards": laggards,
        "movers": movers,
    }


def _build_subject(slot: str, now_local: datetime) -> str:
    label = "RANNÍ" if slot == "morning" else "VEČERNÍ"
    return f"XTB BOT – {label} BRIEFING ({now_local.strftime('%d.%m.%Y')})"


def _render_items(items: Iterable[dict[str, str]], prefix: str = "- ") -> list[str]:
    lines: list[str] = []
    for item in items:
        title = str(item.get("title", "")).strip()
        source = str(item.get("source", "")).strip()
        if not title:
            continue
        if source:
            lines.append(f"{prefix}{title} [{source}]")
        else:
            lines.append(f"{prefix}{title}")
    return lines


def build_email_digest(slot: str = "morning") -> tuple[str, str, dict[str, Any]]:
    now_local = _now_local()
    slot = "evening" if str(slot).strip().lower() == "evening" else "morning"
    subject = _build_subject(slot, now_local)

    world_items = _fetch_google_news("world markets OR stocks OR fed OR inflation when:1d", limit=4)
    geo_items = _fetch_google_news(
        "geopolitics OR sanctions OR taiwan OR china OR russia OR ukraine OR iran OR oil when:1d",
        limit=4,
    )

    portfolio_rows = _portfolio_rows()
    portfolio_summary = _portfolio_summary(portfolio_rows)
    symbols = [str(row.get("symbol", "")).upper().strip() for row in portfolio_rows if str(row.get("symbol", "")).strip()]
    news_map = build_news_sentiment(symbols[:8]) if symbols else {}

    watch_rows: list[dict[str, Any]] = []
    for row in sorted(portfolio_rows, key=lambda x: abs(float(x.get("change_pct", 0.0))), reverse=True):
        symbol = str(row.get("symbol", "")).upper().strip()
        if not symbol:
            continue
        change_pct = round(float(row.get("change_pct", 0.0)), 2)
        if abs(change_pct) < 1.4:
            continue
        sentiment = news_map.get(symbol, {})
        watch_rows.append(
            {
                "symbol": symbol,
                "change_pct": change_pct,
                "price": round(float(row.get("price", 0.0)), 2),
                "trend": str(row.get("trend", "flat")),
                "sentiment": str(sentiment.get("sentiment_label", "neutral")),
                "headline": (sentiment.get("headlines") or [""])[0],
            }
        )
        if len(watch_rows) >= 5:
            break

    lines: list[str] = []
    lines.append(subject)
    lines.append("=" * len(subject))
    lines.append(f"Čas: {now_local.strftime('%d.%m.%Y %H:%M %Z')}")
    lines.append("")

    lines.append("SVĚT")
    lines.extend(_render_items(world_items or [{"title": "Bez nových ověřených světových titulků", "source": "fallback"}]))
    lines.append("")

    lines.append("GEOPOLITIKA")
    lines.extend(_render_items(geo_items or [{"title": "Bez nových ověřených geopolitických titulků", "source": "fallback"}]))
    lines.append("")

    lines.append("AKCIE A PORTFOLIO")
    lines.append(f"- Režim trhu: {portfolio_summary['regime']}")
    lines.append(f"- Zdroj cen: {portfolio_summary['source']}")
    lines.append(f"- Průměrná denní změna sledovaných pozic: {portfolio_summary['avg_change']}%")
    if portfolio_summary["leaders"]:
        leader_line = ", ".join(
            f"{row['symbol']} {round(float(row.get('change_pct', 0.0)), 2)}%"
            for row in portfolio_summary["leaders"]
        )
        lines.append(f"- Nejsilnější pozice: {leader_line}")
    if portfolio_summary["laggards"]:
        laggard_line = ", ".join(
            f"{row['symbol']} {round(float(row.get('change_pct', 0.0)), 2)}%"
            for row in portfolio_summary["laggards"]
        )
        lines.append(f"- Nejslabší pozice: {laggard_line}")
    lines.append("")

    lines.append("CO HNULO PORTFOLIEM")
    if watch_rows:
        for row in watch_rows:
            headline = str(row.get("headline", "")).strip()
            note = f" | zpráva: {headline}" if headline else ""
            lines.append(
                f"- {row['symbol']}: {row['change_pct']}% | cena {row['price']} | trend {row['trend']} | sentiment {row['sentiment']}{note}"
            )
    else:
        lines.append("- Žádná portfolio pozice dnes výrazněji nevybočuje.")
    lines.append("")

    lines.append("POZNÁMKA")
    if slot == "morning":
        lines.append("- Ranní e-mail je čistý briefing: svět, geopolitika a stav tvých akcií před hlavní částí dne.")
    else:
        lines.append("- Večerní e-mail je uzavírací souhrn dne: co se stalo a které tvoje pozice se hýbaly nejvíc.")

    body = "\n".join(lines).strip()
    payload = {
        "slot": slot,
        "subject": subject,
        "body": body,
        "generated_at": now_local.isoformat(),
        "world_items": world_items,
        "geo_items": geo_items,
        "portfolio_watch": watch_rows,
        "portfolio_summary": portfolio_summary,
    }
    return subject, body, payload


def run_email_digest(slot: str = "morning", send: bool = True) -> str:
    slot = "evening" if str(slot).strip().lower() == "evening" else "morning"
    subject, body, payload = build_email_digest(slot)
    now_local = _now_local()
    state = _load_state()
    slot_state = state.get(slot, {}) if isinstance(state.get(slot), dict) else {}
    today_key = now_local.strftime("%Y-%m-%d")
    force = str(os.getenv("EMAIL_DIGEST_FORCE", "false")).strip().lower() in {"1", "true", "yes", "on"}

    delivery = {"delivered": False, "reason": "SEND_DISABLED"}
    if send:
        if slot_state.get("day") == today_key and not force:
            delivery = {"delivered": False, "reason": "ALREADY_SENT_FOR_SLOT"}
        else:
            delivery = send_email_live(subject, body)
            if delivery.get("delivered"):
                state[slot] = {
                    "day": today_key,
                    "sent_at": now_local.isoformat(),
                    "subject": subject,
                }
                _save_state(state)

    OUTPUT_PATH.write_text(body, encoding="utf-8")
    report = [
        f"EMAIL DIGEST ({slot})",
        f"Subject: {subject}",
        f"Status: {'sent' if delivery.get('delivered') else 'not_sent'}",
        f"Reason: {delivery.get('reason', 'OK')}",
        "",
        body,
    ]
    return "\n".join(report)
