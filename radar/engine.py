# radar/engine.py
from __future__ import annotations

import math
import requests
import feedparser
import yfinance as yf
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional

from .features import compute_features, movement_class
from .scoring import compute_score


# ------------------------------------------------------------
# Helpers: config access (bezpečně)
# ------------------------------------------------------------
def cfg_get(cfg: dict, path: str, default=None):
    cur = cfg
    try:
        for p in path.split("."):
            if not isinstance(cur, dict):
                return default
            cur = cur.get(p)
        return default if cur is None else cur
    except Exception:
        return default


def _map_ticker(cfg: dict, t: str) -> str:
    m = cfg_get(cfg, "ticker_map", {}) or {}
    if isinstance(m, dict) and t in m and m[t]:
        return str(m[t]).strip()
    return t


# ------------------------------------------------------------
# Market regime (jednoduchý, stabilní)
# ------------------------------------------------------------
def market_regime(bench: str = "SPY") -> Tuple[str, str]:
    label = "NEUTRÁLNÍ"
    detail = []
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
                elif trend < -0.7:
                    label = "RISK-OFF"

        vix = yf.Ticker("^VIX").history(period="1mo", interval="1d")
        if vix is not None and not vix.empty:
            v = vix["Close"].dropna()
            if len(v) >= 6:
                v_now = float(v.iloc[-1])
                v_5 = float(v.iloc[-6])
                v_ch = (v_now - v_5) / v_5 * 100.0
                detail.append(f"VIX 5D: {v_ch:+.1f}% (aktuálně {v_now:.1f})")
                if v_ch > 10:
                    label = "RISK-OFF"
                elif v_ch < -10 and label != "RISK-OFF":
                    label = "RISK-ON"
    except Exception:
        pass

    return label, "; ".join(detail) if detail else "Bez dostatečných dat."


# ------------------------------------------------------------
# Intraday data (open->last) pro alerty (Yahoo 5m)
# ------------------------------------------------------------
def intraday_open_last(ticker: str) -> Optional[Tuple[float, float]]:
    try:
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h is None or h.empty:
            return None
        o = float(h["Open"].iloc[0])
        last = float(h["Close"].iloc[-1])
        if not math.isfinite(o) or not math.isfinite(last) or o == 0:
            return None
        return o, last
    except Exception:
        return None


def last_close_prev_close(ticker: str) -> Optional[Tuple[float, float]]:
    """Pro 1D % změnu v reportu (Close vs prev Close)."""
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


def pct(new: float, old: float) -> float:
    return ((new - old) / old) * 100.0 if old else 0.0


# ------------------------------------------------------------
# News: RSS (Yahoo + SeekingAlpha + Google News)
# ------------------------------------------------------------
def _rss_entries(url: str, limit: int) -> List[Tuple[str, str]]:
    try:
        feed = feedparser.parse(url)
        out = []
        for e in (feed.entries or [])[:limit]:
            title = (getattr(e, "title", "") or "").strip()
            link = (getattr(e, "link", "") or "").strip()
            if title:
                out.append((title, link))
        return out
    except Exception:
        return []


def news_combined(ticker: str, limit_each: int) -> List[Tuple[str, str, str]]:
    items: List[Tuple[str, str, str]] = []

    # Yahoo RSS
    y = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    items += [("Yahoo", t, l) for t, l in _rss_entries(y, limit_each)]

    # SeekingAlpha RSS
    sa = f"https://seekingalpha.com/symbol/{ticker}.xml"
    items += [("SeekingAlpha", t, l) for t, l in _rss_entries(sa, limit_each)]

    # Google News RSS
    q = requests.utils.quote(f"{ticker} stock OR {ticker} earnings OR {ticker} guidance")
    gn = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    items += [("GoogleNews", t, l) for t, l in _rss_entries(gn, limit_each)]

    # dedupe podle title
    seen = set()
    uniq = []
    for src, title, link in items:
        k = title.lower().strip()
        if k in seen:
            continue
        seen.add(k)
        uniq.append((src, title, link))
    return uniq


WHY_KEYWORDS = [
    (["earnings", "results", "quarter", "beat", "miss"], "Výsledky (earnings) / překvapení vs očekávání"),
    (["guidance", "outlook", "forecast", "raises", "cuts"], "Výhled (guidance) / změna očekávání"),
    (["upgrade", "downgrade", "price target", "rating"], "Analytické doporučení (upgrade/downgrade/cílová cena)"),
    (["acquire", "acquisition", "merger", "deal"], "Akvizice / fúze / transakce"),
    (["sec", "investigation", "lawsuit", "regulator", "antitrust"], "Regulace / vyšetřování / právní zprávy"),
    (["contract", "partnership", "orders"], "Zakázky / partnerství / objednávky"),
    (["chip", "ai", "gpu", "data center", "semiconductor"], "AI/čipy – sektorové zprávy"),
    (["dividend", "buyback", "repurchase"], "Dividenda / buyback"),
]


def why_from_headlines(news_items: List[Tuple[str, str, str]]) -> str:
    if not news_items:
        return "Bez jasné zprávy – může to být sentiment/technika/trh."
    titles = " ".join([t for (_, t, _) in news_items]).lower()
    hits = []
    for keys, reason in WHY_KEYWORDS:
        if any(k in titles for k in keys):
            hits.append(reason)
    return "; ".join(hits[:2]) + "." if hits else "Bez jasné zprávy – může to být sentiment/technika/trh."


# ------------------------------------------------------------
# Core snapshot (radar)
# ------------------------------------------------------------
def run_radar_snapshot(cfg: dict, now: datetime, state=None, universe: Optional[List[str]] = None) -> List[Dict]:
    """
    Vypočítá pro tickery:
    - 1D % (Close vs prev Close)
    - RS 5D-SPY (zjednodušeně: zatím 0; můžeš rozšířit později)
    - vol_ratio (zjednodušeně: 1.0; můžeš rozšířit později)
    - catalyst_score = počet news hitů (0..10)
    - regime_score = podle RISK-ON/OFF
    - movement_class
    - total score (vážené)
    """
    bench = cfg_get(cfg, "benchmarks.spy", "SPY") or "SPY"
    weights = cfg_get(cfg, "weights", {}) or {}

    tickers = universe or []
    # fallback: portfolio/watchlist/new_candidates
    if not tickers:
        pf = cfg_get(cfg, "portfolio", []) or []
        wl = cfg_get(cfg, "watchlist", []) or []
        nc = cfg_get(cfg, "new_candidates", []) or []
        tickers = []
        # portfolio může být list dictů
        if isinstance(pf, list):
            for r in pf:
                if isinstance(r, dict) and r.get("ticker"):
                    tickers.append(str(r["ticker"]).upper())
                elif isinstance(r, str):
                    tickers.append(r.upper())
        if isinstance(wl, list):
            tickers += [str(x).upper() for x in wl if str(x).strip()]
        if isinstance(nc, list):
            tickers += [str(x).upper() for x in nc if str(x).strip()]

    tickers = sorted(set([t.strip().upper() for t in tickers if str(t).strip()]))

    regime_label, regime_detail = market_regime(bench=bench)
    reg_score = 10.0 if regime_label == "RISK-ON" else 0.0 if regime_label == "RISK-OFF" else 5.0

    out: List[Dict] = []

    for t in tickers:
        y = _map_ticker(cfg, t)

        # 1D change
        pct_1d = None
        lc = last_close_prev_close(y)
        if lc:
            last, prev = lc
            pct_1d = pct(last, prev)

        # news + why + catalyst
        news = news_combined(y, int(cfg_get(cfg, "runtime.news_per_ticker", cfg_get(cfg, "NEWS_PER_TICKER", 2)) or 2))
        why = why_from_headlines(news)
        cat = min(10.0, 1.0 + 0.7 * len(news)) if news else 0.0

        # data object pro features
        price_data = {
            "pct_1d": pct_1d,
            "momentum": 0.0 if pct_1d is None else min(10.0, (abs(pct_1d) / 8.0) * 10.0),
            "rel_strength": 0.0,           # můžeš rozšířit (RS 5D-SPY)
            "vol_ratio": 1.0,              # můžeš rozšířit (volume spike)
            "catalyst_score": cat,
            "regime_score": reg_score,
        }

        feats = compute_features(price_data)
        score = compute_score(feats, weights)

        out.append({
            "ticker": t,
            "yahoo": y,
            "pct_1d": pct_1d,
            "movement": feats.get("movement") or movement_class(pct_1d),
            "score": score,
            "regime": regime_label,
            "regime_detail": regime_detail,
            "why": why,
            "news": news,
            "src": "YahooRSS/SA/GoogleRSS",
        })

    return out


# ------------------------------------------------------------
# Alerts snapshot (FIX: 3 args cfg, now, state)
# ------------------------------------------------------------
def run_alerts_snapshot(cfg: dict, now: datetime, state) -> List[Dict]:
    """
    Alerty na změnu >= threshold % od dnešního OPEN (intraday).
    Toto je přesně to, co chceš: 12:00–21:00 okno + každých 15 min kontrola.
    """
    threshold = float(cfg_get(cfg, "runtime.alert_threshold", cfg_get(cfg, "ALERT_THRESHOLD", 3)) or 3)

    # universe = portfolio + watchlist (alerty typicky pro co sleduješ)
    pf = cfg_get(cfg, "portfolio", []) or []
    wl = cfg_get(cfg, "watchlist", []) or []

    tickers = []
    if isinstance(pf, list):
        for r in pf:
            if isinstance(r, dict) and r.get("ticker"):
                tickers.append(str(r["ticker"]).upper())
            elif isinstance(r, str):
                tickers.append(r.upper())
    if isinstance(wl, list):
        tickers += [str(x).upper() for x in wl if str(x).strip()]

    tickers = sorted(set([t.strip().upper() for t in tickers if str(t).strip()]))

    alerts: List[Dict] = []

    for t in tickers:
        y = _map_ticker(cfg, t)
        ol = intraday_open_last(y)
        if not ol:
            continue
        o, last = ol
        ch = pct(last, o)

        if abs(ch) >= threshold:
            alerts.append({
                "ticker": t,
                "yahoo": y,
                "pct_from_open": ch,
                "movement": movement_class(ch),
                "open": o,
                "last": last,
            })

    return alerts