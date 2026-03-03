from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf


@dataclass
class DaytradeSettings:
    orb_minutes: int = 15
    interval: str = "5m"
    mean_reversion_vwap_dev_pct: float = 1.5


def intraday_bars(ticker: str, interval: str = "5m") -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(ticker).history(period="1d", interval=interval)
        if df is None or len(df) < 10:
            return None
        return df
    except Exception:
        return None


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    v = df["Volume"].clip(lower=0)
    pv = (tp * v).cumsum()
    vv = v.cumsum().replace(0, 1)
    return pv / vv


def opening_range(df: pd.DataFrame, orb_minutes: int, interval: str) -> Optional[Tuple[float, float]]:
    # interval "5m" -> 5 min
    try:
        step = int(interval.replace("m", ""))
        bars = max(1, orb_minutes // step)
        sub = df.iloc[:bars]
        if sub is None or len(sub) < 1:
            return None
        return float(sub["High"].max()), float(sub["Low"].min())
    except Exception:
        return None


def vwap_status(df: pd.DataFrame) -> Dict[str, Any]:
    vwap = compute_vwap(df)
    last = float(df["Close"].iloc[-1])
    last_vwap = float(vwap.iloc[-1])
    prev = float(df["Close"].iloc[-2])
    prev_vwap = float(vwap.iloc[-2])

    status = "above_vwap" if last >= last_vwap else "below_vwap"
    signal = None
    if prev < prev_vwap and last >= last_vwap:
        signal = "vwap_reclaim"
    elif prev > prev_vwap and last <= last_vwap:
        signal = "vwap_reject"

    dev_pct = ((last - last_vwap) / last_vwap) * 100.0 if last_vwap else 0.0
    return {"status": status, "signal": signal, "last": last, "vwap": last_vwap, "dev_pct": dev_pct}


def status_for_ticker(ticker: str, s: DaytradeSettings) -> Optional[Dict[str, Any]]:
    df = intraday_bars(ticker, interval=s.interval)
    if df is None:
        return None

    vw = vwap_status(df)
    orr = opening_range(df, s.orb_minutes, s.interval)
    if not orr:
        return None
    orh, orl = orr

    last = float(df["Close"].iloc[-1])
    orb = None
    if last > orh:
        orb = "orb_break_high"
    elif last < orl:
        orb = "orb_break_low"

    # mean reversion hint
    mr = None
    if abs(float(vw["dev_pct"])) >= float(s.mean_reversion_vwap_dev_pct):
        mr = "mean_reversion_to_vwap"

    return {
        "ticker": ticker,
        "last": last,
        "or_high": orh,
        "or_low": orl,
        "vwap": float(vw["vwap"]),
        "vwap_status": vw["status"],
        "vwap_signal": vw["signal"],
        "vwap_dev_pct": float(vw["dev_pct"]),
        "orb_signal": orb,
        "mr_hint": mr,
    }


def daytrade_candidates(tickers: List[str], settings: DaytradeSettings) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in tickers:
        st = status_for_ticker(t, settings)
        if not st:
            continue
        score = 0.0
        if st.get("orb_signal") == "orb_break_high":
            score += 2.0
        if st.get("vwap_signal") == "vwap_reclaim":
            score += 1.5
        if st.get("vwap_status") == "above_vwap":
            score += 0.5
        # penalize strong deviation (chase risk)
        try:
            score -= min(1.5, abs(float(st.get("vwap_dev_pct") or 0.0)) / 2.0)
        except Exception:
            pass
        st["setup_score"] = round(float(score), 3)
        out.append(st)

    out.sort(key=lambda x: float(x.get("setup_score", 0.0)), reverse=True)
    return out