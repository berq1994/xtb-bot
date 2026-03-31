from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from agents.official_company_sources_agent import collect_official_company_news
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


def _first_value(*values: Any) -> float | None:
    for value in values:
        parsed = _safe_float(value)
        if parsed is not None:
            return parsed
    return None


def _statement_value(frame: Any, candidates: list[str]) -> float | None:
    try:
        if frame is None or getattr(frame, 'empty', True):
            return None
        rows = list(getattr(frame, 'index', []) or [])
        cols = list(getattr(frame, 'columns', []) or [])
        if not cols:
            return None
        current_col = cols[0]
        for candidate in candidates:
            for row_name in rows:
                if str(row_name).strip().lower() == candidate.lower():
                    value = frame.loc[row_name, current_col]
                    parsed = _safe_float(value)
                    if parsed is not None:
                        return parsed
    except Exception:
        return None
    return None


def _statement_growth(frame: Any, candidates: list[str]) -> float | None:
    try:
        if frame is None or getattr(frame, 'empty', True):
            return None
        rows = list(getattr(frame, 'index', []) or [])
        cols = list(getattr(frame, 'columns', []) or [])
        if len(cols) < 2:
            return None
        for candidate in candidates:
            for row_name in rows:
                if str(row_name).strip().lower() == candidate.lower():
                    current = _safe_float(frame.loc[row_name, cols[0]])
                    previous = _safe_float(frame.loc[row_name, cols[1]])
                    if current is None or previous in (None, 0):
                        return None
                    return (current - previous) / abs(previous)
    except Exception:
        return None
    return None


def _official_bias(symbol: str, official_by_symbol: dict[str, list[dict[str, Any]]]) -> tuple[str, float, str, str] | None:
    items = official_by_symbol.get(symbol, []) if isinstance(official_by_symbol, dict) else []
    if not items:
        return None
    joined = ' | '.join(str(i.get('title') or '') for i in items[:3]).lower()
    score = 0.0
    reasons: list[str] = []
    if any(k in joined for k in ['quarterly results', 'results & financials', 'earnings', 'financial results', 'annual report']):
        score += 0.25
        reasons.append('načteny oficiální výsledkové materiály')
    if any(k in joined for k in ['guidance', 'outlook', 'revenue', 'profit']):
        score += 0.15
        reasons.append('oficiální materiály zmiňují výhled nebo výsledky')
    if any(k in joined for k in ['governance documents', 'skip to main content']):
        score -= 0.1
    bias = 'positive' if score >= 0.35 else 'neutral'
    return bias, round(score, 2), ', '.join(reasons) or 'Oficiální zdroje byly načteny, ale bez silného fundamentálního signálu.', 'official_sources_proxy'


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
    query = provider_symbol(symbol, "yahoo")
    try:
        ticker = yf.Ticker(query)
    except Exception:
        return None

    info: dict[str, Any] = {}
    try:
        info = ticker.info or {}
    except Exception:
        info = {}
    if not isinstance(info, dict):
        info = {}

    quarterly_income = None
    income = None
    quarterly_balance = None
    balance = None
    fast_info = {}
    try:
        quarterly_income = getattr(ticker, 'quarterly_income_stmt', None)
    except Exception:
        quarterly_income = None
    try:
        income = getattr(ticker, 'income_stmt', None)
    except Exception:
        income = None
    try:
        quarterly_balance = getattr(ticker, 'quarterly_balance_sheet', None)
    except Exception:
        quarterly_balance = None
    try:
        balance = getattr(ticker, 'balance_sheet', None)
    except Exception:
        balance = None
    try:
        fast_info = dict(getattr(ticker, 'fast_info', {}) or {})
    except Exception:
        fast_info = {}

    revenue_growth = _first_value(
        info.get('revenueGrowth'),
        _statement_growth(quarterly_income, ['Total Revenue', 'Operating Revenue', 'Revenue']),
        _statement_growth(income, ['Total Revenue', 'Operating Revenue', 'Revenue']),
    )
    earnings_growth = _first_value(
        info.get('earningsGrowth'),
        _statement_growth(quarterly_income, ['Net Income', 'Net Income Common Stockholders', 'Net Income Including Noncontrolling Interests']),
        _statement_growth(income, ['Net Income', 'Net Income Common Stockholders', 'Net Income Including Noncontrolling Interests']),
    )
    total_debt = _first_value(
        info.get('totalDebt'),
        _statement_value(quarterly_balance, ['Total Debt', 'Long Term Debt And Capital Lease Obligation', 'Long Term Debt']),
        _statement_value(balance, ['Total Debt', 'Long Term Debt And Capital Lease Obligation', 'Long Term Debt']),
    )
    equity = _first_value(
        info.get('totalStockholderEquity'),
        _statement_value(quarterly_balance, ['Stockholders Equity', 'Total Equity Gross Minority Interest', 'Common Stock Equity']),
        _statement_value(balance, ['Stockholders Equity', 'Total Equity Gross Minority Interest', 'Common Stock Equity']),
    )
    debt_to_equity = info.get('debtToEquity')
    if debt_to_equity in (None, '', '-') and total_debt is not None and equity not in (None, 0):
        debt_to_equity = total_debt / equity
    pe_ratio = _first_value(info.get('trailingPE'), fast_info.get('trailingPE'))
    market_cap = _first_value(info.get('marketCap'), fast_info.get('marketCap'))
    roe = _first_value(info.get('returnOnEquity'))

    profile = {
        'companyName': info.get('longName') or info.get('shortName') or symbol,
        'sector': info.get('sector'),
        'industry': info.get('industry'),
        'marketCap': market_cap,
        'pe': pe_ratio,
        'debtToEquity': debt_to_equity,
        'returnOnEquity': roe,
    }
    metrics = {
        'trailingPE': pe_ratio,
        'debtToEquity': debt_to_equity,
        'returnOnEquity': roe,
    }
    growth = {
        'revenueGrowth': revenue_growth,
        'earningsGrowth': earnings_growth,
    }
    has_live = any(v not in (None, '', 0, 0.0) for v in [pe_ratio, debt_to_equity, roe, revenue_growth, earnings_growth, market_cap])
    if not has_live:
        return None
    provider = 'yfinance_stmt' if (revenue_growth is not None or debt_to_equity is not None) else 'yfinance'
    return _build_data(symbol, profile, metrics, growth, provider)

def build_fundamentals_map(symbols: list[str] | None = None) -> dict[str, dict[str, Any]]:
    selected = filter_enabled_symbols(symbols or load_portfolio_symbols(limit=MAX_SYMBOLS))[:MAX_SYMBOLS]
    cache = _load_cache()
    cache.setdefault("symbols", {})
    now = time.time()
    out: dict[str, dict[str, Any]] = {}
    official_by_symbol = collect_official_company_news(selected, limit_per_symbol=2)
    for symbol in selected:
        cached = cache["symbols"].get(symbol, {}) if isinstance(cache["symbols"].get(symbol, {}), dict) else {}
        cached_data = cached.get("data") if isinstance(cached.get("data"), dict) else {}
        cached_provider = str(cached_data.get("provider") or cached_data.get("status") or "").lower()
        cached_has_live = bool(cached_data) and 'fallback' not in cached_provider and 'official_proxy' not in cached_provider
        if cached.get("expires_at", 0) > now and cached_has_live:
            out[symbol] = cached_data
            continue
        data = _yahoo_fetch(symbol) or _fmp_fetch(symbol)
        if not data:
            inferred = _official_bias(symbol, official_by_symbol)
            if inferred is not None:
                bias, score, summary, provider = inferred
                data = _fallback(symbol, status='official_proxy')
                data.update({
                    'provider': provider,
                    'fundamental_bias': bias,
                    'fundamental_score': score,
                    'summary_cs': summary,
                })
            else:
                data = cached_data if isinstance(cached_data, dict) and cached_data else _fallback(symbol)
                data["status"] = data.get("status") or "fallback"
        ttl = CACHE_TTL_SECONDS if 'fallback' not in str(data.get('provider') or data.get('status') or '').lower() else 60 * 60
        cache["symbols"][symbol] = {"expires_at": now + ttl, "data": data}
        out[symbol] = data
        continue
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
