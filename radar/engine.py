from __future__ import annotations

import os
import math
import requests
import yfinance as yf
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional, Any

from radar.features import compute_features, movement_class
from radar.scoring import compute_score


# ============================================================
# CONFIG HELPERS
# ============================================================
def cfg_get(cfg: Any, key: str, default=None):
    try:
        if isinstance(cfg, dict):
            return cfg.get(key, default)
        return getattr(cfg, key, default)
    except Exception:
        return default


# ============================================================
# FMP CLIENT
# ============================================================
FMP_KEY = os.getenv("FMPAPIKEY", "").strip()
FMP_BASE = "https://financialmodelingprep.com/api/v3"


def fmp_get(path: str, params=None):
    if not FMP_KEY:
        return None
    try:
        p = dict(params or {})
        p["apikey"] = FMP_KEY
        r = requests.get(f"{FMP_BASE}/{path}", params=p, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def company_profile(ticker: str) -> Optional[Dict[str, str]]:
    data = fmp_get(f"profile/{ticker}")
    if not data:
        return None
    row = data[0]
    return {
        "name": row.get("companyName") or ticker,
        "sector": row.get("sector") or "",
        "industry": row.get("industry") or "",
    }


def fmp_news(ticker: str, limit: int = 3) -> List[Tuple[str, str, str]]:
    data = fmp_get("stock_news", {"tickers": ticker, "limit": limit})
    if not data:
        return []
    out = []
    for row in data:
        title = row.get("title")
        url = row.get("url")
        if title:
            out.append(("FMP", title, url))
    return out


def is_earnings_today(ticker: str) -> bool:
    cal = fmp_get(f"earning_calendar/{ticker}")
    if not cal:
        return False
    today = date.today().isoformat()
    return any(row.get("date") == today for row in cal)


# ============================================================
# PRICE HELPERS (Yahoo)
# ============================================================
def pct(new: float, old: float) -> float:
    if not old:
        return 0.0
    return ((new - old) / old) * 100.0


def last_close_prev_close(ticker: str) -> Optional[Tuple[float, float]]:
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


def intraday_open_last(ticker: str) -> Optional[Tuple[float, float]]:
    try:
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h is None or h.empty:
            return None
        o = float(h["Open"].iloc[0])
        last = float(h["Close"].iloc[-1])
        if not o:
            return None
        return o, last
    except Exception:
        return None


# ============================================================
# MARKET REGIME (zjednodušený)
# ============================================================
def market_regime() -> Tuple[str, str, float]:
    try:
        spy = yf.Ticker("SPY").history(period="1mo")
        if spy is None or spy.empty:
            return "NEUTRÁLNÍ", "Bez dat", 5.0

        last = float(spy["Close"].iloc[-1])
        ma20 = float(spy["Close"].tail(20).mean())
        trend = pct(last, ma20)

        if trend > 1:
            return "RISK-ON", f"SPY nad MA20 ({trend:+.2f}%)", 10.0
        if trend < -1:
            return "RISK-OFF", f"SPY pod MA20 ({trend:+.2f}%)", 0.0

        return "NEUTRÁLNÍ", f"SPY u MA20 ({trend:+.2f}%)", 5.0

    except Exception:
        return "NEUTRÁLNÍ", "Chyba výpočtu režimu", 5.0


# ============================================================
# RADAR SNAPSHOT
# ============================================================
def run_radar_snapshot(cfg: Any, now: datetime, **kwargs) -> List[Dict]:
    """
    Tolerantní podpis:
    - ignoruje state / universe / reason atd.
    """

    universe = kwargs.get("universe")

    tickers = set()

    if isinstance(cfg, dict):
        for section in ["portfolio", "watchlist", "new_candidates"]:
            rows = cfg.get(section) or []
            for r in rows:
                if isinstance(r, dict) and r.get("ticker"):
                    tickers.add(r["ticker"].upper())
                elif isinstance(r, str):
                    tickers.add(r.upper())

    if universe:
        tickers = set([t.upper() for t in universe])

    tickers = sorted(tickers)

    regime_label, regime_detail, regime_score = market_regime()

    out = []

    for t in tickers:
        lc = last_close_prev_close(t)
        pct_1d = pct(*lc) if lc else None

        news = fmp_news(t, limit=3)
        profile = company_profile(t)
        name = profile["name"] if profile else t

        why = "earnings day" if is_earnings_today(t) else (
            news[0][1] if news else "Bez jasné zprávy"
        )

        raw = {
            "pct_1d": pct_1d,
            "momentum": 0 if pct_1d is None else min(10, abs(pct_1d)),
            "catalyst_score": min(10, len(news) * 2),
            "regime_score": regime_score,
        }

        feats = compute_features(raw)
        score = compute_score(feats, cfg.get("weights") if isinstance(cfg, dict) else {})

        out.append({
            "ticker": t,
            "name": name,
            "pct_1d": pct_1d,
            "movement": movement_class(pct_1d),
            "score": float(score),
            "regime": regime_label,
            "regime_detail": regime_detail,
            "why": why,
            "news": news,
            "src": "FMP",
        })

    return out


# ============================================================
# ALERT SNAPSHOT
# ============================================================
def run_alerts_snapshot(cfg: Any, now: datetime, **kwargs) -> List[Dict]:
    threshold = float(os.getenv("ALERT_THRESHOLD", "3"))

    tickers = set()

    if isinstance(cfg, dict):
        for section in ["portfolio", "watchlist"]:
            rows = cfg.get(section) or []
            for r in rows:
                if isinstance(r, dict) and r.get("ticker"):
                    tickers.add(r["ticker"].upper())
                elif isinstance(r, str):
                    tickers.add(r.upper())

    alerts = []

    for t in sorted(tickers):
        ol = intraday_open_last(t)
        if not ol:
            continue

        o, last = ol
        ch = pct(last, o)

        if abs(ch) >= threshold:
            alerts.append({
                "ticker": t,
                "pct_from_open": ch,
                "movement": movement_class(ch),
                "open": o,
                "last": last,
            })

    return alerts