from __future__ import annotations

import math
from typing import Iterable, Dict, Any, List

DEFAULT_WATCHLIST = ["SPY", "QQQ", "DIA", "IWM", "BTC-USD", "GLD", "TLT", "NVDA", "MSFT", "AAPL"]


def _safe_float(value: Any) -> float | None:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def _fallback_snapshot(symbol: str, idx: int) -> Dict[str, Any]:
    base_price = 100 + idx * 7
    change = round(((idx % 5) - 2) * 0.65, 2)
    trend = "up" if change > 0 else "down" if change < 0 else "flat"
    return {
        "symbol": symbol,
        "price": round(base_price * (1 + change / 100), 2),
        "change_pct": change,
        "trend": trend,
        "source": "fallback",
    }


def _trend_from_series(closes: List[float]) -> str:
    if not closes:
        return "flat"
    if len(closes) < 3:
        return "up" if closes[-1] >= closes[0] else "down"
    sma = sum(closes[-5:]) / min(len(closes), 5)
    last = closes[-1]
    if last > sma * 1.002:
        return "up"
    if last < sma * 0.998:
        return "down"
    return "flat"


def _try_fmp(symbols: List[str]) -> List[Dict[str, Any]]:
    try:
        from production.fmp_market_data import fetch_quotes, fetch_eod_series
    except Exception:
        return []

    quote_map = fetch_quotes(symbols)
    rows: List[Dict[str, Any]] = []
    for symbol in symbols:
        try:
            series = fetch_eod_series(symbol, days_back=12)
        except Exception:
            series = []
        closes = []
        for row in series:
            close = _safe_float(row.get("close"))
            if close is not None:
                closes.append(close)
        price = _safe_float(quote_map.get(str(symbol).upper(), {}).get("price"))
        if price is None and closes:
            price = closes[-1]
        if price is None:
            continue
        prev = closes[-2] if len(closes) >= 2 else float(price)
        change_pct = round(((float(price) - prev) / prev) * 100, 2) if prev else 0.0
        rows.append({
            "symbol": symbol,
            "price": round(float(price), 2),
            "change_pct": change_pct,
            "trend": _trend_from_series(closes or [float(price)]),
            "source": "fmp",
            "closes": closes[-10:],
        })
    return rows


def _try_openbb(symbols: List[str]) -> List[Dict[str, Any]]:
    try:
        from openbb import obb  # type: ignore
    except Exception:
        return []

    rows: List[Dict[str, Any]] = []
    for symbol in symbols:
        try:
            data = obb.equity.price.historical(symbol, provider="yfinance", interval="1d", start_date="2025-01-01")
            df = data.to_df()
            if df is None or len(df) < 2:
                continue
            closes = []
            for x in df["close"].tail(10).tolist():
                v = _safe_float(x)
                if v is not None:
                    closes.append(v)
            if len(closes) < 2:
                continue
            close_now = closes[-1]
            close_prev = closes[-2]
            change_pct = round(((close_now - close_prev) / close_prev) * 100, 2) if close_prev else 0.0
            rows.append({
                "symbol": symbol,
                "price": round(close_now, 2),
                "change_pct": change_pct,
                "trend": _trend_from_series(closes),
                "source": "openbb",
                "closes": closes,
            })
        except Exception:
            continue
    return rows


def _try_yfinance(symbols: List[str]) -> List[Dict[str, Any]]:
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return []
    rows: List[Dict[str, Any]] = []
    for symbol in symbols:
        try:
            hist = yf.Ticker(symbol).history(period="10d", interval="1d")
            if hist is None or hist.empty or len(hist) < 2:
                continue
            closes = []
            for x in hist["Close"].tolist():
                v = _safe_float(x)
                if v is not None:
                    closes.append(v)
            if len(closes) < 2:
                continue
            close_now = closes[-1]
            close_prev = closes[-2]
            change_pct = round(((close_now - close_prev) / close_prev) * 100, 2) if close_prev else 0.0
            rows.append({
                "symbol": symbol,
                "price": round(close_now, 2),
                "change_pct": change_pct,
                "trend": _trend_from_series(closes),
                "source": "yfinance",
                "closes": closes[-10:],
            })
        except Exception:
            continue
    return rows


def _regime_from_rows(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "mixed"
    avg_change = sum(float(r.get("change_pct", 0.0)) for r in rows) / len(rows)
    proxy = {str(r.get("symbol", "")).upper(): r for r in rows}
    score = 0.0
    for sym, weight in [("SPY", 1.0), ("QQQ", 1.0), ("IWM", 0.7), ("BTC-USD", 0.5), ("TLT", -0.3)]:
        row = proxy.get(sym)
        if row:
            score += float(row.get("change_pct", 0.0)) * weight
    composite = (avg_change * 0.6) + (score * 0.4)
    if composite > 0.35:
        return "risk_on"
    if composite < -0.35:
        return "risk_off"
    return "mixed"


def generate_market_overview(watchlist: Iterable[str] | None = None) -> Dict[str, Any]:
    symbols = list(watchlist or DEFAULT_WATCHLIST)

    rows = _try_fmp(symbols)
    if not rows:
        rows = _try_openbb(symbols)
    if not rows:
        rows = _try_yfinance(symbols)
    if not rows:
        rows = [_fallback_snapshot(symbol, idx) for idx, symbol in enumerate(symbols)]

    rows = [r for r in rows if _safe_float(r.get("price")) is not None]
    leaders = sorted(rows, key=lambda x: x.get("change_pct", 0), reverse=True)[:3]
    laggards = sorted(rows, key=lambda x: x.get("change_pct", 0))[:3]
    avg_change = round(sum(r.get("change_pct", 0) for r in rows) / len(rows), 2) if rows else 0.0
    regime = _regime_from_rows(rows)

    return {
        "source": rows[0].get("source", "fallback") if rows else "fallback",
        "symbols": rows,
        "leaders": leaders,
        "laggards": laggards,
        "average_change_pct": avg_change,
        "regime": regime,
    }
