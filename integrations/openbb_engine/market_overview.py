from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Dict, Any, List

DEFAULT_WATCHLIST = ["SPY", "QQQ", "DIA", "IWM", "BTC-USD", "GLD", "TLT", "NVDA", "MSFT", "AAPL"]


def _fallback_snapshot(symbol: str, idx: int) -> Dict[str, Any]:
    base_price = 100 + idx * 7
    change = round(((idx % 5) - 2) * 0.65, 2)
    trend = "up" if change > 0 else "down" if change < 0 else "flat"
    return {
        "symbol": symbol,
        "price": round(base_price * (1 + change / 100), 2),
        "change_pct": change,
        "trend": trend,
        "momentum_5d": change * 1.5,
        "momentum_20d": change * 3.0,
        "distance_to_sma20": change * 0.8,
        "distance_to_sma50": change * 1.1,
        "atr_proxy_pct": max(abs(change) * 0.9, 1.0),
        "source": "fallback",
    }


def _safe_pct(cur: float, base: float) -> float:
    if not base:
        return 0.0
    return round(((cur - base) / base) * 100, 2)


def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _trend_from_series(closes: List[float]) -> str:
    if not closes:
        return "flat"
    if len(closes) < 3:
        return "up" if closes[-1] >= closes[0] else "down"
    sma = _avg(closes[-5:])
    last = closes[-1]
    if last > sma * 1.002:
        return "up"
    if last < sma * 0.998:
        return "down"
    return "flat"


def _row_from_closes(symbol: str, closes: List[float], source: str, price: float | None = None) -> Dict[str, Any] | None:
    if len(closes) < 2:
        return None
    px = float(price if price is not None else closes[-1])
    daily_moves = [_safe_pct(cur, prev) for prev, cur in zip(closes[:-1], closes[1:]) if prev]
    atr_proxy = round(_avg([abs(x) for x in daily_moves[-10:]]) or 1.0, 2)
    sma20 = _avg(closes[-20:]) if len(closes) >= 20 else _avg(closes)
    sma50 = _avg(closes[-50:]) if len(closes) >= 50 else _avg(closes)
    return {
        "symbol": symbol,
        "price": round(px, 2),
        "change_pct": _safe_pct(px, closes[-2]),
        "trend": _trend_from_series(closes),
        "momentum_5d": _safe_pct(px, closes[-6] if len(closes) >= 6 else closes[0]),
        "momentum_20d": _safe_pct(px, closes[-21] if len(closes) >= 21 else closes[0]),
        "distance_to_sma20": _safe_pct(px, sma20) if sma20 else 0.0,
        "distance_to_sma50": _safe_pct(px, sma50) if sma50 else 0.0,
        "atr_proxy_pct": atr_proxy,
        "source": source,
        "closes": closes[-60:],
    }


def _try_fmp(symbols: List[str]) -> List[Dict[str, Any]]:
    try:
        from production.fmp_market_data import fetch_quotes, fetch_eod_series
    except Exception:
        return []

    quote_map = fetch_quotes(symbols)
    rows: List[Dict[str, Any]] = []
    for symbol in symbols:
        try:
            series = fetch_eod_series(symbol, days_back=80)
        except Exception:
            series = []
        closes = [float(row["close"]) for row in series if row.get("close") is not None]
        price = quote_map.get(str(symbol).upper(), {}).get("price")
        row = _row_from_closes(symbol, closes, "fmp", price=float(price) if price is not None else None)
        if row:
            rows.append(row)
    return rows


def _try_openbb(symbols: List[str]) -> List[Dict[str, Any]]:
    try:
        from openbb import obb  # type: ignore
    except Exception:
        return []

    rows: List[Dict[str, Any]] = []
    start_date = (date.today() - timedelta(days=120)).isoformat()
    for symbol in symbols:
        try:
            data = obb.equity.price.historical(symbol, provider="yfinance", interval="1d", start_date=start_date)
            df = data.to_df()
            if df is None or len(df) < 2:
                continue
            closes = [float(x) for x in df["close"].tolist() if x == x]
            row = _row_from_closes(symbol, closes, "openbb")
            if row:
                rows.append(row)
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
            hist = yf.Ticker(symbol).history(period="6mo", interval="1d")
            if hist is None or hist.empty or len(hist) < 2:
                continue
            closes = [float(x) for x in hist["Close"].tolist()]
            row = _row_from_closes(symbol, closes, "yfinance")
            if row:
                rows.append(row)
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
    composite = (avg_change * 0.45) + (score * 0.35)
    trend_bias = sum(float(r.get("momentum_20d", 0.0)) for r in rows[: min(10, len(rows))]) / max(min(10, len(rows)), 1)
    composite += trend_bias * 0.2
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

    leaders = sorted(rows, key=lambda x: x.get("change_pct", 0), reverse=True)[:3]
    laggards = sorted(rows, key=lambda x: x.get("change_pct", 0))[:3]
    avg_change = round(sum(float(r.get("change_pct", 0.0)) for r in rows) / len(rows), 2) if rows else 0.0
    regime = _regime_from_rows(rows)

    return {
        "source": rows[0].get("source", "fallback") if rows else "fallback",
        "symbols": rows,
        "leaders": leaders,
        "laggards": laggards,
        "average_change_pct": avg_change,
        "regime": regime,
    }
