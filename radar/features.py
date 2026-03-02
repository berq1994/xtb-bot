from __future__ import annotations

from typing import Dict, Any

import yfinance as yf


def compute_features(ticker: str) -> Dict[str, Any]:
    # lightweight placeholder: můžeš rozšířit
    try:
        h = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if h is None or len(h) < 20:
            return {"ok": False}
        close = h["Close"]
        ret_20 = float((close.iloc[-1] / close.iloc[-20] - 1.0) * 100.0)
        return {"ok": True, "ret_20": ret_20}
    except Exception:
        return {"ok": False}


def movement_class(pct_1d: float, vol_ratio: float) -> str:
    if abs(pct_1d) >= 4 and vol_ratio >= 1.5:
        return "FAST"
    if abs(pct_1d) >= 2:
        return "MOVE"
    return "CALM"