# radar/engine.py
from __future__ import annotations

import math
import requests
import feedparser
import yfinance as yf
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

from radar.features import compute_features, movement_class
from radar.scoring import compute_score


# ============================================================
# Helpers
# ============================================================

def cfg_get(cfg: Any, path: str, default=None):
    try:
        if isinstance(cfg, dict):
            cur = cfg
            for p in path.split("."):
                if not isinstance(cur, dict):
                    return default
                cur = cur.get(p)
            return default if cur is None else cur

        cur = cfg
        for p in path.split("."):
            cur = getattr(cur, p, None)
            if cur is None:
                return default
        return cur
    except Exception:
        return default


def map_ticker(cfg: Any, t: str) -> str:
    m = cfg_get(cfg, "ticker_map", {}) or {}
    if isinstance(m, dict):
        return m.get(t, t)
    return t


def pct(new: float, old: float) -> float:
    if not old:
        return 0.0
    return ((new - old) / old) * 100.0


def safe_float(x) -> Optional[float]:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


# ============================================================
# Market regime
# ============================================================

def market_regime(bench: str = "SPY") -> Tuple[str, str, float]:
    label = "NEUTRÁLNÍ"
    detail = []
    score = 5.0

    try:
        spy = yf.Ticker(bench).history(period="3mo", interval="1d")
        if spy is not None and not spy.empty:
            close = spy["Close"].dropna()
            if len(close) >= 25:
                c0 = float(close.iloc[-1])
                ma20 = float(close.tail(20).mean())
                trend = (c0 - ma20) / ma20 * 100.0
                detail.append(f"{bench} vs MA20: {trend:+.2f}%")

                if trend > 0.7:
                    label = "RISK-ON"
                    score = 10.0
                elif trend < -0.7:
                    label = "RISK-OFF"
                    score = 0.0

        vix = yf.Ticker("^VIX").history(period="1mo", interval="1d")
        if vix is not None and not vix.empty:
            v = vix["Close"].dropna()
            if len(v) >= 6:
                v_now = float(v.iloc[-1])
                v_5 = float(v.iloc[-6])
                v_ch = (v_now - v_5) / v_5 * 100.0
                detail.append(f"VIX 5D: {v_ch:+.1f}% ({v_now:.1f})")

    except Exception:
        pass

    return label, ("; ".join(detail) if detail else "Bez dat"), score


# ============================================================
# Prices
# ============================================================

def last_close_prev_close(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="10d", interval="1d")
        if h is None or h.empty:
            return None
        c = h["Close"].dropna()
        if len(c) < 2:
            return None
        return float(c.iloc[-1]), float(c.iloc[-2])
    except Exception:
        return None


def intraday_open_last(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h is None or h.empty:
            return None
        o = safe_float(h["Open"].iloc[0])
        last = safe_float(h["Close"].iloc[-1])
        if o and last:
            return o, last
    except Exception:
        pass
    return None


def volume_ratio_1d(ticker: str) -> float:
    try:
        h = yf.Ticker(ticker).history(period="2mo", interval="1d")
        if h is None or h.empty:
            return 1.0
        v = h["Volume"].dropna()
        return float(v.iloc[-1]) / float(v.tail(20).mean())
    except Exception:
        return 1.0


# ============================================================
# News
# ============================================================

def news_combined(ticker: str, limit_each: int):
    items = []
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}"
    feed = feedparser.parse(url)
    for e in (feed.entries or [])[:limit_each]:
        items.append(("Yahoo", e.title, e.link))
    return items


def why_from_headlines(news_items):
    if news_items:
        return "Zachyceny zprávy / zvýšená aktivita"
    return "Bez výrazných zpráv"


# ============================================================
# SNAPSHOT
# ============================================================

def run_radar_snapshot(cfg: Any, now: datetime, reason="snapshot"):
    tickers = set()

    for row in cfg_get(cfg, "portfolio", []):
        if isinstance(row, dict):
            tickers.add(row["ticker"])

    regime_label, regime_detail, regime_score = market_regime()

    out = []

    for t in sorted(tickers):
        y = map_ticker(cfg, t)

        pct_1d = None
        lc = last_close_prev_close(y)
        if lc:
            pct_1d = pct(lc[0], lc[1])

        raw = {
            "pct_1d": pct_1d,
            "momentum": 0 if pct_1d is None else abs(pct_1d),
            "vol_ratio": volume_ratio_1d(y),
            "catalyst_score": 0,
            "regime_score": regime_score,
        }

        feats = compute_features(raw)
        score = compute_score(feats, cfg_get(cfg, "weights", {}))

        out.append({
            "ticker": t,
            "resolved": y,
            "pct_1d": pct_1d,
            "score": score,
            "class": feats.get("movement"),
            "why": why_from_headlines([]),
        })

    return out


# ============================================================
# ALERTS
# ============================================================

def run_alerts_snapshot(cfg: Any, now: datetime, st):
    threshold = float(cfg_get(cfg, "alert_threshold_pct", 3.0))

    alerts = []

    for row in cfg_get(cfg, "portfolio", []):
        t = row["ticker"]
        y = map_ticker(cfg, t)

        ol = intraday_open_last(y)
        if not ol:
            continue

        ch = pct(ol[1], ol[0])

        if abs(ch) >= threshold:
            alerts.append({
                "ticker": t,
                "resolved": y,
                "pct_from_open": ch,
                "open": ol[0],
                "last": ol[1],
            })

    return alerts