from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from symbol_utils import filter_enabled_symbols

from agents.portfolio_context_agent import load_portfolio_symbols
from integrations.openbb_engine import build_news_sentiment, generate_market_overview
from knowledge.company_memory import load_company_dossier, sync_company_memory
from knowledge.evidence_scoring import score_news_items
from knowledge.playbooks import ensure_seed_playbooks, evaluate_playbooks_for_item
from knowledge.study_library import ensure_seed_studies, match_studies_for_item
from agents.signal_quality_agent import build_action_queue, score_actionability

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

try:
    from agents.learning_agent import load_signal_weights
except Exception:  # pragma: no cover
    def load_signal_weights() -> dict:
        return {
            "trend": 1.0,
            "momentum": 1.0,
            "sentiment": 1.0,
            "regime_alignment": 1.0,
            "risk_penalty": 1.0,
            "evidence_quality": 1.0,
            "playbook_alignment": 1.0,
            "study_alignment": 1.0,
        }

WATCHLIST_PATH = Path("config/watchlists/google_finance_watchlist.json")
PORTFOLIO_PATH = Path("config/portfolio_state.json")
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
    return filter_enabled_symbols(str(s).strip() for s in symbols if str(s).strip())


def _load_portfolio_meta() -> dict[str, dict]:
    if not PORTFOLIO_PATH.exists():
        return {}
    try:
        payload = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    accounts = payload.get("accounts", {}) if isinstance(payload, dict) else {}
    if not isinstance(accounts, dict):
        return {}

    meta: dict[str, dict] = {}
    for account_name, account in accounts.items():
        if not isinstance(account, dict):
            continue
        for item in account.get("positions", []):
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).strip().upper()
            if not symbol:
                continue
            row = meta.setdefault(symbol, {"themes": set(), "value": 0.0, "avg_price": None, "accounts": [], "name": None})
            row["value"] += float(item.get("value") or 0.0)
            avg_price = item.get("avg_price")
            if avg_price is not None and row.get("avg_price") is None:
                try:
                    row["avg_price"] = float(avg_price)
                except (TypeError, ValueError):
                    pass
            themes = item.get("theme", [])
            if isinstance(themes, list):
                row["themes"].update(str(t).strip() for t in themes if str(t).strip())
            row["accounts"].append(account_name)
            if item.get("name") and row.get("name") is None:
                row["name"] = str(item.get("name")).strip()

    normalized: dict[str, dict] = {}
    for symbol, row in meta.items():
        normalized[symbol] = {
            "themes": sorted(row["themes"]),
            "value": round(float(row["value"]), 2),
            "avg_price": row.get("avg_price"),
            "accounts": row.get("accounts", []),
            "name": row.get("name") or symbol,
        }
    return normalized


def _theme_counts(meta: dict[str, dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in meta.values():
        for theme in row.get("themes", []):
            counts[theme] = counts.get(theme, 0) + 1
    return counts


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
        sym = str(symbol).strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        merged.append(sym)
    return filter_enabled_symbols(merged)


def _sentiment_weight(label: str) -> float:
    return {
        "positive": 0.8,
        "neutral": 0.15,
        "negative": -0.8,
    }.get(str(label).strip(), 0.0)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _regime_alignment(regime: str, trend: str, change_pct: float) -> float:
    if regime == "risk_on":
        if trend == "up" and change_pct >= 0:
            return 0.55
        if trend == "down":
            return -0.35
    if regime == "risk_off":
        if trend == "down":
            return 0.25
        if trend == "up":
            return -0.35
    return 0.1 if trend == "up" else 0.0


def _category_for(item: dict) -> str:
    if item["held"] and item["sentiment_label"] == "negative":
        return "portfolio_defense"
    if item["held"] and item.get("pnl_vs_cost_pct") is not None and float(item["pnl_vs_cost_pct"]) > 12:
        return "winner_management"
    if item["held"] and item.get("pnl_vs_cost_pct") is not None and float(item["pnl_vs_cost_pct"]) < -8:
        return "drawdown_control"
    if "earnings" in item.get("catalysts", []):
        return "earnings_watch"
    if item["sentiment_label"] == "negative":
        return "risk_watch"
    if item["trend"] == "up" and item["momentum_5d"] > 1.2:
        return "breakout_watch"
    if item["trend"] == "down" and item["held"]:
        return "pullback_control"
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
    ensure_seed_studies()
    ensure_seed_playbooks()
    sync_company_memory()

    resolved_watchlist = _resolve_watchlist(watchlist)
    overview = generate_market_overview(resolved_watchlist)
    rows = overview.get("symbols", [])
    portfolio_symbols = set(load_portfolio_symbols(limit=50))
    portfolio_meta = _load_portfolio_meta()
    theme_counts = _theme_counts(portfolio_meta)
    symbols_ranked_for_news = sorted(
        rows,
        key=lambda r: (
            1 if str(r.get("symbol", "")).strip().upper() in portfolio_symbols else 0,
            abs(float(r.get("change_pct", 0.0) or 0.0)),
        ),
        reverse=True,
    )
    symbols = [str(r.get("symbol", "")).strip().upper() for r in symbols_ranked_for_news if str(r.get("symbol", "")).strip()]
    news_map = build_news_sentiment(symbols)
    weights = load_signal_weights()

    ranked: list[dict] = []
    for row in rows:
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        change_pct = float(row.get("change_pct", 0.0))
        trend = str(row.get("trend", "flat"))
        price = float(row.get("price", 0.0))
        momentum_5d = float(row.get("momentum_5d", 0.0))
        momentum_20d = float(row.get("momentum_20d", 0.0))
        atr_proxy_pct = float(row.get("atr_proxy_pct", 1.0) or 1.0)
        sentiment = news_map.get(symbol, {})
        sentiment_label = str(sentiment.get("sentiment_label", "neutral"))
        sentiment_score = float(sentiment.get("sentiment_score", 0.0))
        held = symbol in portfolio_symbols
        meta = portfolio_meta.get(symbol, {})
        avg_cost = meta.get("avg_price")
        pnl_vs_cost_pct = None
        if avg_cost not in (None, 0, 0.0):
            pnl_vs_cost_pct = round(((price - float(avg_cost)) / float(avg_cost)) * 100, 2)

        overlap_penalty = 0.0
        for theme in meta.get("themes", []):
            count = int(theme_counts.get(theme, 0))
            if count >= 3:
                overlap_penalty += 0.12
            elif count == 2:
                overlap_penalty += 0.05

        item = {
            "symbol": symbol,
            "name": meta.get("name") or sentiment.get("company_hint") or symbol,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "trend": trend,
            "momentum_5d": round(momentum_5d, 2),
            "momentum_20d": round(momentum_20d, 2),
            "atr_proxy_pct": round(atr_proxy_pct, 2),
            "held": held,
            "themes": meta.get("themes", []),
            "accounts": meta.get("accounts", []),
            "position_value": meta.get("value", 0.0),
            "avg_cost": avg_cost,
            "pnl_vs_cost_pct": pnl_vs_cost_pct,
            "sentiment_label": sentiment_label,
            "sentiment_score": sentiment_score,
            "category": "watchlist_monitor",
            "priority_score": 0.0,
            "headlines": sentiment.get("headlines", [])[:3],
            "reasons": sentiment.get("reasons", [])[:3],
            "catalysts": sentiment.get("catalysts", []),
            "news_count": int(sentiment.get("news_count", 0) or 0),
            "source_count": int(sentiment.get("source_count", 0) or 0),
            "regime_alignment": 0.0,
            "theme_overlap_penalty": round(overlap_penalty, 2),
            "news_items": sentiment.get("items", []),
        }
        item["category"] = _category_for(item)
        evidence = score_news_items(item.get("news_items", []))
        dossier = load_company_dossier(symbol, fallback_name=item.get("name"), themes=item.get("themes", []))
        item["company_memory"] = {
            "name": dossier.get("name"),
            "sector_hints": dossier.get("sector_hints", []),
            "key_catalysts": dossier.get("key_catalysts", [])[:3],
            "key_risks": dossier.get("key_risks", [])[:3],
            "thesis": dossier.get("thesis"),
        }
        item["evidence_score"] = evidence.get("score", 0.0)
        item["evidence_grade"] = evidence.get("grade", "D")
        item["trusted_sources"] = evidence.get("trusted_sources", [])
        item["news_providers"] = evidence.get("providers", [])
        item["evidence_reasons"] = evidence.get("reasons", [])
        regime_fit = _regime_alignment(str(overview.get("regime", "mixed")), trend, change_pct)
        item["regime_alignment"] = round(regime_fit, 2)
        studies = match_studies_for_item(item, str(overview.get("regime", "mixed")))
        item["study_alignment_score"] = studies.get("alignment_score", 0.0)
        item["matched_studies"] = studies.get("matched", [])
        item["study_notes"] = studies.get("notes", [])
        playbooks = evaluate_playbooks_for_item(item, str(overview.get("regime", "mixed")))
        item["playbook_score"] = playbooks.get("match_score", 0.0)
        item["playbooks"] = playbooks.get("matches", [])

        score = 0.0
        score += _clip(abs(change_pct) / 1.5, 0.0, 2.2) * float(weights.get("momentum", 1.0))
        score += _clip(momentum_5d / 2.5, -1.2, 1.6) * float(weights.get("trend", 1.0))
        score += _clip(momentum_20d / 6.0, -1.0, 1.4) * float(weights.get("trend", 1.0))
        score += _sentiment_weight(sentiment_label) * float(weights.get("sentiment", 1.0))
        score += _clip(sentiment_score / 6.0, -0.6, 0.8)
        score += regime_fit * float(weights.get("regime_alignment", 1.0))
        score -= overlap_penalty * float(weights.get("risk_penalty", 1.0))
        score += item["evidence_score"] * float(weights.get("evidence_quality", 1.0))
        score += item["playbook_score"] * float(weights.get("playbook_alignment", 1.0))
        score += item["study_alignment_score"] * float(weights.get("study_alignment", 1.0))
        score += 1.0 if held else 0.2
        score += 0.2 if atr_proxy_pct <= 2.5 else -0.1
        item["priority_score"] = round(score, 2)
        ranked.append(item)

    for item in ranked:
        item.update(score_actionability(item, str(overview.get('regime', 'mixed'))))

    ranked.sort(key=lambda x: x["priority_score"], reverse=True)
    top_items = ranked[:10]
    action_queue = build_action_queue(top_items, str(overview.get('regime', 'mixed')), limit=5)
    external_items = _external_modules()

    state = {
        "regime": overview.get("regime", "mixed"),
        "source": overview.get("source", "unknown"),
        "watchlist_size": len(resolved_watchlist),
        "portfolio_symbols": sorted(portfolio_symbols),
        "top_items": top_items,
        "action_queue": action_queue,
        "all_items": ranked,
        "external_items": external_items,
        "weights_used": weights,
    }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("LIVE RESEARCH")
    lines.append(f"Režim trhu: {overview.get('regime', 'mixed')}")
    lines.append(f"Zdroj dat: {overview.get('source', 'unknown')}")
    lines.append(f"Velikost watchlistu: {len(resolved_watchlist)}")
    lines.append("")
    lines.append("Akční fronta:")
    if action_queue:
        for item in action_queue:
            lines.append(
                f"- {item['symbol']} | akčnost {item['actionability_score']} | bucket {item['action_bucket']} | score {item['priority_score']} | kategorie {item['category']}"
            )
            lines.append(f"  · podnět: {item.get('action_hint', '')}")
            if item.get('headline_cs'):
                lines.append(f"  · zpráva: {item['headline_cs']}")
    else:
        lines.append("- Bez nové akční položky nad prahovou hodnotou.")
    lines.append("")

    lines.append("Hlavní priority:")
    for item in top_items:
        holding = "ano" if item["held"] else "ne"
        pnl = f" | P/L vs nákup {item['pnl_vs_cost_pct']}%" if item.get("pnl_vs_cost_pct") is not None else ""
        playbook_titles = ", ".join(str(p.get("title")) for p in item.get("playbooks", [])[:2])
        study_titles = ", ".join(str(s.get("title")) for s in item.get("matched_studies", [])[:2])
        lines.append(
            f"- {item['symbol']} | score {item['priority_score']} | pohyb {item['change_pct']}% | 5d {item['momentum_5d']}% | trend {item['trend']} | sentiment {item['sentiment_label']} | evidence {item['evidence_grade']} ({item['evidence_score']}) | držená pozice {holding} | kategorie {item['category']}{pnl}"
        )
        if playbook_titles:
            lines.append(f"  · playbook: {playbook_titles}")
        if study_titles:
            lines.append(f"  · studie: {study_titles}")
        if item.get("trusted_sources"):
            lines.append(f"  · zdroje: {', '.join(item['trusted_sources'][:3])}")
        for reason in item.get("reasons", [])[:1]:
            lines.append(f"  · news logika: {reason}")
        for reason in item.get("evidence_reasons", [])[:1]:
            lines.append(f"  · evidence: {reason}")
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
