from __future__ import annotations

from typing import Iterable, Dict, Any, List
import math

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
        "source": "fallback",
    }


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
            close_now = float(df["close"].iloc[-1])
            close_prev = float(df["close"].iloc[-2])
            change_pct = round(((close_now - close_prev) / close_prev) * 100, 2) if close_prev else 0.0
            trend = "up" if close_now > float(df["close"].tail(5).mean()) else "down"
            rows.append({
                "symbol": symbol,
                "price": round(close_now, 2),
                "change_pct": change_pct,
                "trend": trend,
                "source": "openbb",
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
            hist = yf.Ticker(symbol).history(period="5d", interval="1d")
            if hist is None or hist.empty or len(hist) < 2:
                continue
            close_now = float(hist["Close"].iloc[-1])
            close_prev = float(hist["Close"].iloc[-2])
            sma = float(hist["Close"].mean())
            change_pct = round(((close_now - close_prev) / close_prev) * 100, 2) if close_prev else 0.0
            trend = "up" if close_now > sma else "down"
            rows.append({
                "symbol": symbol,
                "price": round(close_now, 2),
                "change_pct": change_pct,
                "trend": trend,
                "source": "yfinance",
            })
        except Exception:
            continue
    return rows


def generate_market_overview(watchlist: Iterable[str] | None = None) -> Dict[str, Any]:
    symbols = list(watchlist or DEFAULT_WATCHLIST)

    rows = _try_openbb(symbols)
    if not rows:
        rows = _try_yfinance(symbols)
    if not rows:
        rows = [_fallback_snapshot(symbol, idx) for idx, symbol in enumerate(symbols)]

    leaders = sorted(rows, key=lambda x: x.get("change_pct", 0), reverse=True)[:3]
    laggards = sorted(rows, key=lambda x: x.get("change_pct", 0))[:3]
    avg_change = round(sum(r.get("change_pct", 0) for r in rows) / len(rows), 2) if rows else 0.0

    if avg_change > 0.35:
        regime = "risk_on"
    elif avg_change < -0.35:
        regime = "risk_off"
    else:
        regime = "mixed"

    return {
        "source": rows[0].get("source", "fallback") if rows else "fallback",
        "symbols": rows,
        "leaders": leaders,
        "laggards": laggards,
        "average_change_pct": avg_change,
        "regime": regime,
    }
