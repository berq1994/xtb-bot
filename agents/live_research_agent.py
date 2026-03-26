from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from agents.portfolio_context_agent import load_portfolio_symbols
from integrations.openbb_engine import build_news_sentiment, generate_market_overview

try:
    from agents.corporate_research_agent import run_corporate_research
except Exception:  # pragma: no cover
    run_corporate_research = None

try:
    from agents.macro_research_agent import run_macro_research
except Exception:  # pragma: no cover
    run_macro_research = None

try:
    from agents.earnings_research_agent import run_earnings_research
except Exception:  # pragma: no cover
    run_earnings_research = None

try:
    from agents.geo_research_agent import run_geo_research
except Exception:  # pragma: no cover
    run_geo_research = None

WATCHLIST_PATH = Path("config/watchlists/google_finance_watchlist.json")
STATE_PATH = Path("data/research_live_state.json")
REPORT_PATH = Path("research_live_report.txt")


def _load_default_watchlist() -> list[str]:
    if not WATCHLIST_PATH.exists():
        return []
    try:
        payload = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    symbols = payload.get("symbols", [])
    if not isinstance(symbols, list):
        return []
    return [str(s).strip() for s in symbols if str(s).strip()]


def _resolve_watchlist(watchlist: Iterable[str] | None = None) -> list[str]:
    if watchlist:
        resolved = [str(s).strip() for s in watchlist if str(s).strip()]
        if resolved:
            return resolved

    defaults = _load_default_watchlist()
    portfolio = load_portfolio_symbols(limit=20)

    merged: list[str] = []
    seen: set[str] = set()
    for symbol in [*portfolio, *defaults]:
        sym = str(symbol).strip()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        merged.append(sym)
    return merged


def _sentiment_weight(label: str) -> float:
    return {
        "positive": 0.55,
        "neutral": 0.15,
        "negative": -0.45,
    }.get(str(label).strip(), 0.0)


def _category_for(symbol: str, change_pct: float, held: bool, sentiment_label: str) -> str:
    if held:
        return "portfolio_priority"
    if change_pct <= -1.2 and sentiment_label != "negative":
        return "pullback_watch"
    if change_pct >= 1.2 and sentiment_label != "negative":
        return "breakout_watch"
    if sentiment_label == "negative":
        return "risk_watch"
    return "watchlist_monitor"


def _external_modules() -> list[dict]:
    items: list[dict] = []
    for name, runner in [
        ("macro", run_macro_research),
        ("corporate", run_corporate_research),
        ("earnings", run_earnings_research),
        ("geo", run_geo_research),
    ]:
        if runner is None:
            continue
        try:
            payload = runner()
        except Exception as exc:  # pragma: no cover
            payload = {"ok": False, "error": str(exc), "items": []}
        if not isinstance(payload, dict):
            continue
        entries = payload.get("items", [])
        if not isinstance(entries, list):
            entries = []
        for item in entries[:2]:
            headline = str(item.get("headline") or item.get("title") or "")
            summary = str(item.get("summary") or item.get("body") or "")
            impact = float(item.get("impact") or item.get("impact_score") or 0.0)
            relevance = float(item.get("relevance") or item.get("relevance_score") or 0.0)
            items.append(
                {
                    "source": name,
                    "headline": headline,
                    "summary": summary,
                    "impact": round(impact, 2),
                    "relevance": round(relevance, 2),
                }
            )
    return items


def run_live_research(watchlist: Iterable[str] | None = None) -> str:
    resolved_watchlist = _resolve_watchlist(watchlist)
    overview = generate_market_overview(resolved_watchlist)
    rows = overview.get("symbols", [])
    portfolio_symbols = set(load_portfolio_symbols(limit=50))
    symbols = [str(r.get("symbol", "")).strip() for r in rows if str(r.get("symbol", "")).strip()]
    news_map = build_news_sentiment(symbols)

    ranked: list[dict] = []
    for row in rows:
        symbol = str(row.get("symbol", "")).strip()
        if not symbol:
            continue
        change_pct = float(row.get("change_pct", 0.0))
        trend = str(row.get("trend", "flat"))
        price = float(row.get("price", 0.0))
        sentiment = news_map.get(symbol, {})
        sentiment_label = str(sentiment.get("sentiment_label", "neutral"))
        held = symbol in portfolio_symbols
        score = abs(change_pct) * 0.85
        score += 1.1 if held else 0.25
        score += 0.35 if trend == "up" else 0.15 if trend == "flat" else 0.05
        score += _sentiment_weight(sentiment_label)
        category = _category_for(symbol, change_pct, held, sentiment_label)
        ranked.append(
            {
                "symbol": symbol,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "trend": trend,
                "held": held,
                "sentiment_label": sentiment_label,
                "sentiment_score": float(sentiment.get("sentiment_score", 0.0)),
                "category": category,
                "priority_score": round(score, 2),
                "headlines": sentiment.get("headlines", [])[:2],
            }
        )

    ranked.sort(key=lambda x: x["priority_score"], reverse=True)
    top_items = ranked[:8]
    external_items = _external_modules()

    state = {
        "regime": overview.get("regime", "mixed"),
        "source": overview.get("source", "unknown"),
        "watchlist_size": len(resolved_watchlist),
        "portfolio_symbols": sorted(portfolio_symbols),
        "top_items": top_items,
        "external_items": external_items,
    }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("LIVE RESEARCH")
    lines.append(f"Režim trhu: {overview.get('regime', 'mixed')}")
    lines.append(f"Zdroj dat: {overview.get('source', 'unknown')}")
    lines.append(f"Velikost watchlistu: {len(resolved_watchlist)}")
    lines.append("")
    lines.append("Hlavní priority:")
    for item in top_items:
        holding = "ano" if item["held"] else "ne"
        lines.append(
            f"- {item['symbol']} | score {item['priority_score']} | pohyb {item['change_pct']}% | trend {item['trend']} | sentiment {item['sentiment_label']} | držená pozice {holding} | kategorie {item['category']}"
        )
        for headline in item.get("headlines", [])[:2]:
            lines.append(f"  • {headline}")
    lines.append("")
    lines.append("Doplňkové výzkumné vrstvy:")
    if external_items:
        for item in external_items[:6]:
            lines.append(
                f"- {item['source']}: {item['headline']} | impact {item['impact']} | relevance {item['relevance']}"
            )
    else:
        lines.append("- Bez doplňkových modulů")

    output = "\n".join(lines).strip()
    REPORT_PATH.write_text(output, encoding="utf-8")
    return output
