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


# ------------------------
# Helpers
# ------------------------
def cfg_get(cfg: Any, path: str, default=None):
    """
    cfg může být:
      - dict (config z yaml)
      - nebo objekt (dataclass)
    """
    try:
        if isinstance(cfg, dict):
            cur = cfg
            for p in path.split("."):
                if not isinstance(cur, dict):
                    return default
                cur = cur.get(p)
            return default if cur is None else cur

        # objekt (cfg.xxx)
        cur = cfg
        for p in path.split("."):
            cur = getattr(cur, p, None)
            if cur is None:
                return default
        return cur
    except Exception:
        return default


def _ticker_map(cfg: Any) -> Dict[str, str]:
    m = cfg_get(cfg, "ticker_map", {}) or {}
    return m if isinstance(m, dict) else {}


def map_ticker(cfg: Any, t: str) -> str:
    m = _ticker_map(cfg)
    return m.get(t, t)


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


# ------------------------
# Market regime (SPY trend + VIX)
# ------------------------
def market_regime(bench: str = "SPY") -> Tuple[str, str, float]:
    """
    Vrací (label, detail, regime_score 0..10)
    """
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
                else:
                    label = "NEUTRÁLNÍ"
                    score = 5.0

        vix = yf.Ticker("^VIX").history(period="1mo", interval="1d")
        if vix is not None and not vix.empty:
            v = vix["Close"].dropna()
            if len(v) >= 6:
                v_now = float(v.iloc[-1])
                v_5 = float(v.iloc[-6])
                v_ch = (v_now - v_5) / v_5 * 100.0
                detail.append(f"VIX 5D: {v_ch:+.1f}% (aktuálně {v_now:.1f})")
                # pokud VIX roste hodně, přepni do risk-off
                if v_ch > 10:
                    label = "RISK-OFF"
                    score = 0.0
                elif v_ch < -10 and label != "RISK-OFF":
                    label = "RISK-ON"
                    score = 10.0

    except Exception:
        pass

    return label, ("; ".join(detail) if detail else "Bez dostatečných dat."), score


# ------------------------
# Prices
# ------------------------
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
        o = safe_float(h["Open"].iloc[0])
        last = safe_float(h["Close"].iloc[-1])
        if o is None or last is None or o == 0:
            return None
        return o, last
    except Exception:
        return None


def volume_ratio_1d(ticker: str) -> float:
    """
    Poměr objemu posledního dne vs průměr 20 dní.
    Když nejde, vrátí 1.0.
    """
    try:
        h = yf.Ticker(ticker).history(period="2mo", interval="1d")
        if h is None or h.empty or "Volume" not in h:
            return 1.0
        v = h["Volume"].dropna()
        if len(v) < 10:
            return 1.0
        avg20 = float(v.tail(20).mean())
        lastv = float(v.iloc[-1])
        if avg20 <= 0:
            return 1.0
        return lastv / avg20
    except Exception:
        return 1.0


# ------------------------
# News (RSS)
# ------------------------
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

    # SeekingAlpha RSS (public feed)
    sa = f"https://seekingalpha.com/symbol/{ticker}.xml"
    items += [("SeekingAlpha", t, l) for t, l in _rss_entries(sa, limit_each)]

    # Google News RSS search
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
    (["earnings", "results", "quarter", "beat", "miss"], "výsledky (earnings) / překvapení vs očekávání"),
    (["guidance", "outlook", "forecast", "raises", "cuts"], "výhled (guidance) / změna očekávání"),
    (["upgrade", "downgrade", "price target", "rating"], "analytické doporučení (upgrade/downgrade/cílová cena)"),
    (["acquire", "acquisition", "merger", "deal"], "akvizice / fúze / transakce"),
    (["sec", "investigation", "lawsuit", "regulator", "antitrust"], "regulace / vyšetřování / právní zprávy"),
    (["contract", "partnership", "orders"], "zakázky / partnerství / objednávky"),
    (["chip", "ai", "gpu", "data center", "semiconductor"], "AI/čipy – sektorové zprávy"),
    (["dividend", "buyback", "repurchase"], "dividenda / buyback"),
]


def why_from_headlines(news_items: List[Tuple[str, str, str]]) -> str:
    if not news_items:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    titles = " ".join([t for (_, t, _) in news_items]).lower()
    hits = []
    for keys, reason in WHY_KEYWORDS:
        if any(k in titles for k in keys):
            hits.append(reason)
    return "; ".join(hits[:2]) + "." if hits else "bez jasné zprávy – může to být sentiment/technika/trh."


# ------------------------
# Public API
# ------------------------
def run_radar_snapshot(cfg: Any, now: datetime, reason: str = "snapshot") -> List[Dict[str, Any]]:
    """
    Vrátí list řádků pro reporting.
    Používá:
      - portfolio + watchlist + new_candidates
      - weights
      - benchmark SPY
    """
    bench = cfg_get(cfg, "benchmarks.spy", "SPY") or "SPY"
    weights = cfg_get(cfg, "weights", {}) or {}

    # tickery
    tickers = set()

    pf = cfg_get(cfg, "portfolio", []) or []
    wl = cfg_get(cfg, "watchlist", []) or []
    nc = cfg_get(cfg, "new_candidates", []) or []

    if isinstance(pf, list):
        for r in pf:
            if isinstance(r, dict) and r.get("ticker"):
                tickers.add(str(r["ticker"]).strip().upper())
            elif isinstance(r, str):
                tickers.add(r.strip().upper())

    if isinstance(wl, list):
        for x in wl:
            tickers.add(str(x).strip().upper())

    if isinstance(nc, list):
        for x in nc:
            tickers.add(str(x).strip().upper())

    tickers = sorted([t for t in tickers if t])

    regime_label, regime_detail, regime_score = market_regime(bench=bench)

    limit_each = int(cfg_get(cfg, "cache_ttl_sec", 900) or 900)  # jen aby něco existovalo
    # NEWS_PER_TICKER nemáme vždy v cfg, takže fallback 2:
    news_per = int(cfg_get(cfg, "news_per_ticker", 2) or 2)
    if isinstance(cfg, dict):
        # v dict configu to bude běžně jinde – necháme fallback
        pass

    out: List[Dict[str, Any]] = []

    for t in tickers:
        y = map_ticker(cfg, t)

        pct_1d = None
        lc = last_close_prev_close(y)
        if lc:
            last, prev = lc
            pct_1d = pct(last, prev)

        # momentum score (0..10)
        momentum = 0.0 if pct_1d is None else min(10.0, (abs(pct_1d) / 8.0) * 10.0)

        vol_ratio = volume_ratio_1d(y)

        news = news_combined(y, news_per)
        why = why_from_headlines(news)
        catalyst = 0.0
        if news:
            catalyst = min(10.0, 1.0 + 0.7 * len(news))

        raw = {
            "pct_1d": pct_1d,
            "momentum": momentum,
            "rel_strength": 0.0,       # zatím jednoduché (můžeš rozšířit)
            "vol_ratio": vol_ratio,
            "catalyst_score": catalyst,
            "regime_score": regime_score,
        }

        feats = compute_features(raw)
        score = compute_score(feats, weights)

        out.append({
            "ticker": t,
            "yahoo": y,
            "pct_1d": pct_1d,
            "movement": feats.get("movement") or movement_class(pct_1d),
            "score": float(score),
            "regime": regime_label,
            "regime_detail": regime_detail,
            "why": why,
            "news": news,
            "src": "RSS",
        })

    return out


def run_alerts_snapshot(cfg: Any, now: datetime, st) -> List[Dict[str, Any]]:
    """
    ✅ DŮLEŽITÉ: podpis má být (cfg, now, st) – přesně jak to voláš v mainu.

    Alerty jsou od dnešního OPEN (5m data z Yahoo).
    Dedupe/anti-spam řeší tvůj State objekt (st).
    """
    threshold = float(cfg_get(cfg, "alert_threshold_pct", 3.0) or 3.0)

    # tickery pro alerty: portfolio + watchlist
    tickers = set()

    pf = cfg_get(cfg, "portfolio", []) or []
    wl = cfg_get(cfg, "watchlist", []) or []

    if isinstance(pf, list):
        for r in pf:
            if isinstance(r, dict) and r.get("ticker"):
                tickers.add(str(r["ticker"]).strip().upper())
            elif isinstance(r, str):
                tickers.add(r.strip().upper())

    if isinstance(wl, list):
        for x in wl:
            tickers.add(str(x).strip().upper())

    tickers = sorted([t for t in tickers if t])

    alerts: List[Dict[str, Any]] = []

    for t in tickers:
        y = map_ticker(cfg, t)
        ol = intraday_open_last(y)
        if not ol:
            continue
        o, last = ol
        ch = pct(last, o)

        if abs(ch) >= threshold:
            # dedupe přes state (pokud existuje metoda should_alert)
            # necháváme tolerantní – když metoda neexistuje, alert pošleme.
            key = f"{t}|{round(ch,2)}"
            if hasattr(st, "should_alert"):
                try:
                    if not st.should_alert(t, key, now.strftime("%Y-%m-%d")):
                        continue
                except Exception:
                    pass

            alerts.append({
                "ticker": t,
                "yahoo": y,
                "pct_from_open": ch,
                "movement": movement_class(ch),
                "open": o,
                "last": last,
            })

    return alerts