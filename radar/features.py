# radar/features.py
from __future__ import annotations

from typing import Dict, Any
import math
import yfinance as yf


def compute_features(ticker: str) -> Dict[str, Any]:
    """
    Zjednodušené features pro scoring:
    - trend (close vs MA20)
    - volatility (ATR aproximace)
    """
    out: Dict[str, Any] = {"ok": False}

    try:
        h = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if h is None or len(h) < 30:
            return out

        close = h["Close"]
        high = h["High"]
        low = h["Low"]

        ma20 = float(close.rolling(20).mean().iloc[-1])
        last = float(close.iloc[-1])

        # ATR-ish: průměr (high-low)/close za 14 dní
        tr = (high - low) / close
        atr14 = float(tr.tail(14).mean())

        out.update(
            {
                "ok": True,
                "last": last,
                "ma20": ma20,
                "trend_up": last > ma20 if ma20 else False,
                "atr14": atr14,
            }
        )
        return out
    except Exception:
        return out


def movement_class(pct_1d: float, vol_ratio: float) -> str:
    """
    Hrubá klasifikace pohybu (pro levels).
    """
    try:
        p = float(pct_1d)
        v = float(vol_ratio)
    except Exception:
        return "NORMAL"

    if abs(p) >= 6 and v >= 1.5:
        return "BIG_MOVE"
    if abs(p) >= 3 and v >= 1.2:
        return "MOVE"
    if v >= 2.0:
        return "VOLUME_SPIKE"
    return "NORMAL"