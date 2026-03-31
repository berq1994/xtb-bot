
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from symbol_utils import filter_enabled_symbols

from agents.data_integrity_agent import build_data_health_summary, validate_symbols
from agents.portfolio_context_agent import load_portfolio_symbols
from integrations.openbb_engine import build_news_sentiment, generate_market_overview
from knowledge.company_memory import load_company_dossier, sync_company_memory, update_company_memory_from_research_state
from knowledge.evidence_scoring import score_news_items
from knowledge.playbooks import ensure_seed_playbooks, evaluate_playbooks_for_item
from knowledge.study_library import ensure_seed_studies, match_studies_for_item
from agents.signal_quality_agent import build_action_queue, score_actionability
from agents.technical_analysis_agent import build_technical_analysis_map
from agents.official_company_sources_agent import collect_official_company_news
from agents.fundamentals_agent import build_fundamentals_map
from agents.macro_calendar_agent import load_macro_calendar
from currency_utils import native_value_to_czk

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
THESIS_UPDATES_PATH = Path("data/thesis_updates.json")


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
            row = meta.setdefault(symbol, {"themes": set(), "value": 0.0, "value_czk": 0.0, "avg_price": None, "accounts": [], "name": None, "quantity": 0.0, "currencies": set()})
            native_value = float(item.get("value") or 0.0)
            row["value"] += native_value
            row["value_czk"] += native_value_to_czk(native_value, item.get("ccy") or item.get("currency"))
            row["quantity"] += float(item.get("quantity") or item.get("qty") or 0.0)
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
            row["currencies"].add(str(item.get("ccy") or item.get("currency") or "").strip().upper())
            if item.get("name") and row.get("name") is None:
                row["name"] = str(item.get("name")).strip()

    normalized: dict[str, dict] = {}
    for symbol, row in meta.items():
        normalized[symbol] = {
            "themes": sorted(row["themes"]),
            "value": round(float(row["value"]), 2),
            "value_czk": round(float(row["value_czk"]), 2),
            "quantity": round(float(row["quantity"]), 4),
            "avg_price": row.get("avg_price"),
            "accounts": row.get("accounts", []),
            "currencies": sorted(row.get("currencies", [])),
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
            return validate_symbols(resolved).get('valid_symbols', resolved)

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
    return validate_symbols(filter_enabled_symbols(merged)).get('valid_symbols', merged)


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
            items.append({"source": name, "headline": headline, "summary": summary, "impact": round(impact, 2), "relevance": round(relevance, 2)})
    return items


def _thesis_strength_from_dossier(dossier: dict) -> float:
    strength = 0.25
    if dossier.get('key_catalysts'):
        strength += 0.15
    if dossier.get('key_risks'):
        strength += 0.15
    thesis = str(dossier.get('thesis') or '').strip()
    if thesis and 'Neutrální výchozí teze' not in thesis:
        strength += 0.25
    if dossier.get('latest_observations'):
        strength += 0.1
    if dossier.get('watch_for'):
        strength += 0.1
    return round(min(1.0, strength), 2)


def _build_risk_summary(items: list[dict]) -> dict:
    held = [i for i in items if i.get('held')]
    if not held:
        return {'held_count': 0, 'concentration_warning': False, 'top_themes': [], 'defense_names': []}
    total_value = sum(float(i.get('position_value_czk', i.get('position_value', 0.0)) or 0.0) for i in held) or 1.0
    biggest = max(held, key=lambda x: float(x.get('position_value_czk', x.get('position_value', 0.0)) or 0.0))
    concentration = round((float(biggest.get('position_value_czk', biggest.get('position_value', 0.0)) or 0.0) / total_value) * 100, 2)
    theme_count: dict[str, int] = {}
    defense_names: list[str] = []
    for item in held:
        for theme in item.get('themes', []):
            theme_count[theme] = theme_count.get(theme, 0) + 1
        if str(item.get('category')) in {'portfolio_defense', 'drawdown_control'}:
            defense_names.append(str(item.get('symbol')))
    top_themes = sorted(theme_count.items(), key=lambda kv: kv[1], reverse=True)[:4]
    return {
        'held_count': len(held),
        'largest_position_symbol': str(biggest.get('symbol')),
        'largest_position_share_pct': concentration,
        'concentration_warning': concentration >= 22.0,
        'top_themes': top_themes,
        'defense_names': defense_names[:5],
    }


def run_live_research(watchlist: Iterable[str] | None = None) -> str:
    ensure_seed_studies()
    ensure_seed_playbooks()
    sync_company_memory()

    resolved_watchlist = _resolve_watchlist(watchlist)
    overview = generate_market_overview(resolved_watchlist)
    rows = overview.get("symbols", [])
    health = build_data_health_summary(rows)
    rows = health.get('rows', rows)
    portfolio_symbols = set(load_portfolio_symbols(limit=50))
    portfolio_meta = _load_portfolio_meta()
    theme_counts = _theme_counts(portfolio_meta)
    symbols_ranked_for_news = sorted(
        rows,
        key=lambda r: (
            1 if str(r.get("symbol", "")).strip().upper() in portfolio_symbols else 0,
            float(r.get('data_quality_score', 0.0) or 0.0),
            abs(float(r.get("change_pct", 0.0) or 0.0)),
        ),
        reverse=True,
    )
    symbols = [str(r.get("symbol", "")).strip().upper() for r in symbols_ranked_for_news if str(r.get("symbol", "")).strip()]
    news_map = build_news_sentiment(symbols)
    official_map = collect_official_company_news(symbols[:6])
    ta_map = build_technical_analysis_map(symbols[:8])
    fundamentals_map = build_fundamentals_map(symbols[:8])
    macro_state = load_macro_calendar(7)
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
        official_items = official_map.get(symbol, []) if isinstance(official_map.get(symbol, []), list) else []
        merged_news_items = list(official_items) + list(sentiment.get("items", []))
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
            "position_value_czk": meta.get("value_czk", 0.0),
            "quantity": meta.get('quantity', 0.0),
            "avg_cost": avg_cost,
            "pnl_vs_cost_pct": pnl_vs_cost_pct,
            "sentiment_label": sentiment_label,
            "sentiment_score": sentiment_score,
            "category": "watchlist_monitor",
            "priority_score": 0.0,
            "headlines": ([item.get("title", "") for item in official_items[:2]] + sentiment.get("headlines", []))[:3],
            "reasons": sentiment.get("reasons", [])[:3],
            "catalysts": sentiment.get("catalysts", []),
            "news_count": int(sentiment.get("news_count", 0) or 0) + len(official_items),
            "source_count": max(int(sentiment.get("source_count", 0) or 0), 0) + (1 if official_items else 0),
            "regime_alignment": 0.0,
            "theme_overlap_penalty": round(overlap_penalty, 2),
            "news_items": merged_news_items,
            "official_items": official_items,
            "official_item_count": len(official_items),
            'data_quality_score': float(row.get('data_quality_score', 0.0) or 0.0),
            'data_quality_label': str(row.get('data_quality_label', 'ok')),
            'data_quality_reasons': row.get('data_quality_reasons', []),
            'source': row.get('source', overview.get('source', 'unknown')),
        }
        item["category"] = _category_for(item)
        ta = ta_map.get(symbol, {}) if isinstance(ta_map.get(symbol, {}), dict) else {}
        evidence = score_news_items(item.get("news_items", []))
        dossier = load_company_dossier(symbol, fallback_name=item.get("name"), themes=item.get("themes", []))
        thesis_strength = _thesis_strength_from_dossier(dossier)
        item["company_memory"] = {
            "name": dossier.get("name"),
            "sector_hints": dossier.get("sector_hints", []),
            "key_catalysts": dossier.get("key_catalysts", [])[:3],
            "key_risks": dossier.get("key_risks", [])[:3],
            "thesis": dossier.get("thesis"),
            'watch_for': dossier.get('watch_for', [])[:3],
        }
        item['thesis_strength'] = thesis_strength
        item['technical'] = ta
        item['technical_setup'] = str(ta.get('setup_type', 'none'))
        item['technical_regime'] = str(ta.get('trend_regime', 'unknown'))
        item['ta_score'] = float(ta.get('ta_score', 0.0) or 0.0)
        item['buy_decision'] = str(ta.get('buy_decision', 'watch'))
        item['buy_trigger'] = str(ta.get('buy_trigger', ''))
        item['scenario_bull'] = str(ta.get('scenario_bull', ''))
        item['scenario_base'] = str(ta.get('scenario_base', ''))
        item['scenario_bear'] = str(ta.get('scenario_bear', ''))
        item["evidence_score"] = evidence.get("score", 0.0)
        item["evidence_grade"] = evidence.get("grade", "D")
        item["trusted_sources"] = evidence.get("trusted_sources", [])
        item["news_providers"] = evidence.get("providers", [])
        item["evidence_reasons"] = evidence.get("reasons", [])
        fundamentals = fundamentals_map.get(symbol, {}) if isinstance(fundamentals_map.get(symbol, {}), dict) else {}
        item["fundamentals"] = fundamentals
        item["fundamental_provider"] = str(fundamentals.get("provider", fundamentals.get("status", "fallback")))
        item["fundamental_bias"] = str(fundamentals.get("fundamental_bias", "neutral"))
        item["fundamental_score"] = float(fundamentals.get("fundamental_score", 0.0) or 0.0)
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
        score += (thesis_strength - 0.45)
        score += (item['data_quality_score'] - 0.55) * 1.1
        score += max(0.0, item['ta_score'] - 4.5) * 0.32
        score += min(0.35, len(official_items) * 0.15)
        score += item['fundamental_score'] * 0.45
        if 'fallback' in str(item.get('fundamental_provider', '')).lower():
            score -= 0.12
        if str(macro_state.get('macro_risk', 'low')) == 'high' and item['category'] in {'breakout_watch', 'watchlist_monitor'}:
            score -= 0.2
        if item['buy_decision'] in {'buy_breakout', 'buy_pullback'}:
            score += 0.45
        elif item['buy_decision'] == 'buy_reversal':
            score += 0.2
        elif item['buy_decision'] == 'avoid' and not held:
            score -= 0.35
        score += 1.0 if held else 0.2
        score += 0.2 if atr_proxy_pct <= 2.5 else -0.1
        item["priority_score"] = round(score, 2)
        ranked.append(item)

    for item in ranked:
        item.update(score_actionability(item, str(overview.get('regime', 'mixed'))))

    ranked.sort(key=lambda x: (
        1 if bool(x.get('held')) else 0,
        float(x.get('priority_score', 0.0) or 0.0),
        float(x.get('data_quality_score', 0.0) or 0.0),
    ), reverse=True)
    top_items = ranked[:10]
    action_queue = build_action_queue(top_items, str(overview.get('regime', 'mixed')), limit=5)
    external_items = _external_modules()
    risk_summary = _build_risk_summary(ranked)

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
        'data_health': {'avg_quality': health.get('avg_quality'), 'counts': health.get('counts')},
        'risk_summary': risk_summary,
        'official_source_count': sum(len(v) for v in official_map.values()),
        'technical_summary': {k: {'setup': v.get('setup_type'), 'decision': v.get('buy_decision'), 'ta_score': v.get('ta_score')} for k, v in ta_map.items()},
        'fundamentals_summary': {k: {'bias': v.get('fundamental_bias'), 'score': v.get('fundamental_score')} for k, v in fundamentals_map.items()},
        'macro_calendar': macro_state,
    }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    mem_update = update_company_memory_from_research_state(state)
    THESIS_UPDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    THESIS_UPDATES_PATH.write_text(json.dumps({
        'generated_from': 'live_research',
        'updated_symbols': mem_update.get('updated_symbols', 0),
        'top_symbols': [str(i.get('symbol')) for i in top_items[:5]],
        'risk_summary': risk_summary,
        'official_source_count': sum(len(v) for v in official_map.values()),
        'technical_summary': {k: {'setup': v.get('setup_type'), 'decision': v.get('buy_decision'), 'ta_score': v.get('ta_score')} for k, v in ta_map.items()},
        'fundamentals_summary': {k: {'bias': v.get('fundamental_bias'), 'score': v.get('fundamental_score')} for k, v in fundamentals_map.items()},
        'macro_calendar': macro_state,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = []
    lines.append("LIVE RESEARCH")
    lines.append(f"Režim trhu: {overview.get('regime', 'mixed')}")
    lines.append(f"Zdroj dat: {overview.get('source', 'unknown')}")
    lines.append(f"Velikost watchlistu: {len(resolved_watchlist)}")
    lines.append(f"Datová kvalita: {health.get('avg_quality', 0.0)} | good {health.get('counts', {}).get('good', 0)} | ok {health.get('counts', {}).get('ok', 0)} | weak {health.get('counts', {}).get('weak', 0)} | bad {health.get('counts', {}).get('bad', 0)}")
    lines.append("")
    lines.append("Akční fronta:")
    if action_queue:
        for item in action_queue:
            lines.append(
                f"- {item['symbol']} | akčnost {item['actionability_score']} | bucket {item['action_bucket']} | urgence {item.get('urgency_label')} | score {item['priority_score']} | kategorie {item['category']}"
            )
            lines.append(f"  · podnět: {item.get('action_hint', '')}")
            if item.get('buy_decision') and item.get('buy_decision') != 'watch':
                lines.append(f"  · technika: {item.get('buy_decision')} | trigger {item.get('buy_trigger', '')}")
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
            f"- {item['symbol']} | score {item['priority_score']} | pohyb {item['change_pct']}% | 5d {item['momentum_5d']}% | trend {item['trend']} | sentiment {item['sentiment_label']} | evidence {item['evidence_grade']} ({item['evidence_score']}) | data {item['data_quality_label']} ({item['data_quality_score']}) | TA {item.get('technical_setup')} {item.get('ta_score')} | akce {item.get('buy_decision')} | držená pozice {holding} | kategorie {item['category']}{pnl}"
        )
        if playbook_titles:
            lines.append(f"  · playbook: {playbook_titles}")
        if study_titles:
            lines.append(f"  · studie: {study_titles}")
        if item.get("trusted_sources"):
            lines.append(f"  · zdroje: {', '.join(item['trusted_sources'][:3])}")
        if item.get('official_item_count'):
            lines.append(f"  · oficiální zdroje: {item.get('official_item_count')} | trigger: {item.get('buy_trigger', '')}")
        if item.get('fundamentals', {}).get('summary_cs'):
            lines.append(f"  · fundamenty: {item.get('fundamentals', {}).get('summary_cs')}")
        thesis = str(item.get('company_memory', {}).get('thesis') or '').strip()
        if thesis:
            lines.append(f"  · teze: {thesis[:140]}")
        for reason in item.get("reasons", [])[:1]:
            lines.append(f"  · news logika: {reason}")
        for reason in item.get("evidence_reasons", [])[:1]:
            lines.append(f"  · evidence: {reason}")
        if item.get('scenario_bull'):
            lines.append(f"  · scénář+: {item.get('scenario_bull')}")
        if item.get('scenario_bear'):
            lines.append(f"  · scénář-: {item.get('scenario_bear')}")
    lines.append("")
    lines.append("Makro vrstva:")
    lines.append(f"- Riziko kalendáře: {macro_state.get('macro_risk', '-')}")
    for event in (macro_state.get('events', []) if isinstance(macro_state, dict) else [])[:3]:
        lines.append(f"  · {event.get('date')} | {event.get('country')} | {event.get('event')}")
    lines.append("")
    lines.append("Riziková vrstva:")
    lines.append(f"- Počet držených pozic ve výzkumu: {risk_summary.get('held_count', 0)}")
    lines.append(f"- Největší pozice: {risk_summary.get('largest_position_symbol', '-')} | podíl {risk_summary.get('largest_position_share_pct', 0)}%")
    lines.append(f"- Koncentrační varování: {'ano' if risk_summary.get('concentration_warning') else 'ne'}")
    if risk_summary.get('top_themes'):
        lines.append('- Hlavní témata: ' + ', '.join(f"{k} ({v})" for k, v in risk_summary.get('top_themes', [])))
    if risk_summary.get('defense_names'):
        lines.append('- Obranně sledované pozice: ' + ', '.join(risk_summary.get('defense_names', [])))
    lines.append("")
    lines.append("Doplňkové výzkumné vrstvy:")
    lines.append(f"- Oficiální firemní položky načtené v běhu: {sum(len(v) for v in official_map.values())}")
    if external_items:
        for item in external_items[:6]:
            lines.append(f"- {item['source']}: {item['headline']} | impact {item['impact']} | relevance {item['relevance']}")
    else:
        lines.append("- Bez doplňkových modulů")

    output = "\n".join(lines).strip()
    REPORT_PATH.write_text(output, encoding="utf-8")
    return output
