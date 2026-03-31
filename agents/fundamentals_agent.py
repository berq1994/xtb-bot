from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from agents.portfolio_context_agent import load_portfolio_symbols
from symbol_utils import filter_enabled_symbols, provider_symbol

CACHE_PATH = Path("data/fundamentals_cache.json")
STATE_PATH = Path("data/fundamentals_state.json")
REPORT_PATH = Path("fundamentals_report.txt")
CACHE_TTL_SECONDS = 60 * 60 * 24
MAX_SYMBOLS = 8
TIMEOUT = 6


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


def _fmp_get(path: str, params: dict[str, Any]) -> Any:
    api_key = str(os.getenv("FMP_API_KEY") or os.getenv("FMPAPIKEY") or "").strip()
    if not api_key:
        return None
    try:
        response = requests.get(
            f"https://financialmodelingprep.com/stable/{path}",
            params={**params, "apikey": api_key},
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; XTBResearchBot/1.0)"},
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except Exception:
        return None


def _bias_from_payload(profile: dict[str, Any], metrics: dict[str, Any], growth: dict[str, Any]) -> tuple[str, float, str]:
    score = 0.0
    reasons: list[str] = []
    market_cap = _safe_float(profile.get("marketCap")) or 0.0
    pe = _safe_float(metrics.get("peRatioTTM") or metrics.get("trailingPE") or profile.get("pe") or profile.get("trailingPE")) or 0.0
    debt_to_equity = _safe_float(metrics.get("debtToEquityTTM") or metrics.get("debtToEquity") or profile.get("debtToEquity")) or 0.0
    roe = _safe_float(metrics.get("roeTTM") or metrics.get("returnOnEquity") or profile.get("returnOnEquity")) or 0.0
    revenue_growth = _safe_float(growth.get("growthRevenue") or growth.get("revenueGrowth")) or 0.0
    net_income_growth = _safe_float(growth.get("growthNetIncome") or growth.get("netIncomeGrowth") or growth.get("earningsGrowth")) or 0.0
    if revenue_growth > 0.05:
        score += 0.6
        reasons.append("tržby rostou")
    elif revenue_growth < -0.03:
        score -= 0.6
        reasons.append("tržby slábnou")
    if net_income_growth > 0.05:
        score += 0.5
        reasons.append("ziskovost roste")
    elif net_income_growth < -0.03:
        score -= 0.5
        reasons.append("ziskovost slábne")
    if 0 < roe < 0.08:
        score -= 0.2
    elif roe >= 0.08:
        score += 0.3
        reasons.append("ROE je zdravé")
    if debt_to_equity and debt_to_equity > 1.8:
        score -= 0.7
        reasons.append("vyšší zadlužení")
    elif debt_to_equity and debt_to_equity < 0.8:
        score += 0.2
    if pe:
        if pe > 45:
            score -= 0.35
            reasons.append("valuace je náročná")
        elif 0 < pe < 22:
            score += 0.2
    if market_cap and market_cap > 50_000_000_000:
        score += 0.1
    if score >= 0.55:
        return "positive", round(score, 2), ", ".join(reasons) or "fundamenty vyznívají podpůrně"
    if score <= -0.55:
        return "negative", round(score, 2), ", ".join(reasons) or "fundamenty vyznívají slabě"
    return "neutral", round(score, 2), ", ".join(reasons) or "fundamenty bez výrazné převahy"


def _fallback(symbol: str, status: str = "fallback") -> dict[str, Any]:
    return {
        "symbol": symbol,
        "status": status,
        "provider": status,
        "fundamental_bias": "neutral",
        "fundamental_score": 0.0,
        "summary_cs": "Fundamentální vrstva nemá dost live dat; výchozí neutrální pohled.",
        "revenue_growth": None,
        "net_income_growth": None,
        "debt_to_equity": None,
        "pe_ratio": None,
        "roe": None,
    }


def _build_data(symbol: str, profile: dict[str, Any], metrics: dict[str, Any], growth: dict[str, Any], provider: str) -> dict[str, Any]:
    bias, score, reason = _bias_from_payload(profile, metrics, growth)
    pe = _safe_float(metrics.get("peRatioTTM") or metrics.get("trailingPE") or profile.get("pe") or profile.get("trailingPE"))
    debt = _safe_float(metrics.get("debtToEquityTTM") or metrics.get("debtToEquity") or profile.get("debtToEquity"))
    roe = _safe_float(metrics.get("roeTTM") or metrics.get("returnOnEquity") or profile.get("returnOnEquity"))
    rev = _safe_float(growth.get("growthRevenue") or growth.get("revenueGrowth"))
    ni = _safe_float(growth.get("growthNetIncome") or growth.get("netIncomeGrowth") or growth.get("earningsGrowth"))
    return {
        "symbol": symbol,
        "status": "ok",
        "provider": provider,
        "name": profile.get("companyName") or profile.get("longName") or symbol,
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "market_cap": profile.get("marketCap"),
        "fundamental_bias": bias,
        "fundamental_score": score,
        "summary_cs": reason,
        "revenue_growth": round(rev * 100, 2) if rev is not None else None,
        "net_income_growth": round(ni * 100, 2) if ni is not None else None,
        "debt_to_equity": round(debt, 2) if debt is not None else None,
        "pe_ratio": round(pe, 2) if pe is not None else None,
        "roe": round(roe * 100, 2) if roe is not None and abs(roe) <= 2 else round(roe, 2) if roe is not None else None,
    }


def _fmp_fetch(symbol: str) -> dict[str, Any] | None:
    query = provider_symbol(symbol, "fmp")
    profile_rows = _fmp_get("profile", {"symbol": query})
    metrics_rows = _fmp_get("key-metrics-ttm", {"symbol": query})
    growth_rows = _fmp_get("income-statement-growth", {"symbol": query, "limit": 1})
    profile = profile_rows[0] if isinstance(profile_rows, list) and profile_rows else {}
    metrics = metrics_rows[0] if isinstance(metrics_rows, list) and metrics_rows else {}
    growth = growth_rows[0] if isinstance(growth_rows, list) and growth_rows else {}
    if not (profile or metrics or growth):
        return None
    return _build_data(symbol, profile, metrics, growth, "fmp")


def _yahoo_fetch(symbol: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        ticker = yf.Ticker(provider_symbol(symbol, "yahoo"))
        info = ticker.info or {}
    except Exception:
        info = {}
    if not isinstance(info, dict) or not info:
        return None
    profile = {
        "companyName": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "marketCap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "debtToEquity": info.get("debtToEquity"),
        "returnOnEquity": info.get("returnOnEquity"),
    }
    metrics = {
        "trailingPE": info.get("trailingPE"),
        "debtToEquity": info.get("debtToEquity"),
        "returnOnEquity": info.get("returnOnEquity"),
    }
    growth = {
        "revenueGrowth": info.get("revenueGrowth"),
        "earningsGrowth": info.get("earningsGrowth"),
    }
    has_live = any(v not in (None, "", 0, 0.0) for v in [
        info.get("trailingPE"), info.get("debtToEquity"), info.get("returnOnEquity"), info.get("revenueGrowth"), info.get("earningsGrowth"), info.get("marketCap")
    ])
    if not has_live:
        return None
    return _build_data(symbol, profile, metrics, growth, "yfinance")


def build_fundamentals_map(symbols: list[str] | None = None) -> dict[str, dict[str, Any]]:
    selected = filter_enabled_symbols(symbols or load_portfolio_symbols(limit=MAX_SYMBOLS))[:MAX_SYMBOLS]
    cache = _load_cache()
    cache.setdefault("symbols", {})
    now = time.time()
    out: dict[str, dict[str, Any]] = {}
    for symbol in selected:
        cached = cache["symbols"].get(symbol, {}) if isinstance(cache["symbols"].get(symbol, {}), dict) else {}
        if cached.get("expires_at", 0) > now and isinstance(cached.get("data"), dict):
            out[symbol] = cached["data"]
            continue
        data = _yahoo_fetch(symbol) or _fmp_fetch(symbol)
        if not data:
            data = cached.get("data") if isinstance(cached.get("data"), dict) else _fallback(symbol)
            data["status"] = data.get("status") or "fallback"
        cache["symbols"][symbol] = {"expires_at": now + CACHE_TTL_SECONDS, "data": data}
        out[symbol] = data
    _save_cache(cache)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_fundamentals(symbols: list[str] | None = None) -> str:
    data = build_fundamentals_map(symbols)
    lines = ["FUNDAMENTÁLNÍ VRSTVA"]
    for symbol, item in data.items():
        provider = str(item.get("provider") or item.get("status") or "-")
        revenue = item.get("revenue_growth") if item.get("revenue_growth") is not None else "-"
        lines.append(
            f"- {symbol} | bias {item.get('fundamental_bias')} | score {item.get('fundamental_score')} | provider {provider} | PE {item.get('pe_ratio') or '-'} | D/E {item.get('debt_to_equity') or '-'} | růst tržeb {revenue}%"
        )
        if item.get("summary_cs"):
            lines.append(f"  · {item.get('summary_cs')}")
    if len(lines) == 1:
        lines.append("Bez fundamentálních dat.")
    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    return report
