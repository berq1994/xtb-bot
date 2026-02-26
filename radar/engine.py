# radar/engine.py
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
import feedparser
import yfinance as yf

from radar.config import RadarConfig
from radar.universe import resolved_universe
from radar.features import compute_features, movement_class
from radar.scoring import compute_score
from radar.levels import pick_level


def map_ticker(cfg: RadarConfig, t: str) -> str:
    return (cfg.ticker_map.get(t) or t).strip()


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


# ---------- Market regime ----------
def market_regime(cfg: RadarConfig) -> Tuple[str, str, float]:
    bench = cfg.benchmarks.get("spy", "SPY")
    vix_t = cfg.benchmarks.get("vix", "^VIX")

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
                    label, score = "RISK-ON", 10.0
                elif trend < -0.7:
                    label, score = "RISK-OFF", 0.0

        vix = yf.Ticker(vix_t).history(period="1mo", interval="1d")
        if vix is not None and not vix.empty:
            v = vix["Close"].dropna()
            if len(v) >= 6:
                v_now = float(v.iloc[-1])
                v_5 = float(v.iloc[-6])
                v_ch = (v_now - v_5) / v_5 * 100.0
                detail.append(f"VIX 5D: {v_ch:+.1f}% (aktuálně {v_now:.1f})")
                if v_ch > 10:
                    label, score = "RISK-OFF", 0.0
                elif v_ch < -10 and label != "RISK-OFF":
                    label, score = "RISK-ON", 10.0
    except Exception:
        pass

    return label, ("; ".join(detail) if detail else "Bez dostatečných dat."), score


# ---------- Prices ----------
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


# ---------- Company name (cache přes State) ----------
def resolve_company_name(yahoo_ticker: str, st=None) -> str:
    if st is not None:
        cached = st.get_name(yahoo_ticker)
        if cached:
            return cached

    name = ""
    try:
        info = yf.Ticker(yahoo_ticker).get_info()
        name = (info.get("longName") or info.get("shortName") or "").strip()
    except Exception:
        name = ""

    if st is not None and name:
        st.set_name(yahoo_ticker, name)
    return name or "—"


# ---------- News ----------
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


def news_combined(yahoo_ticker: str, limit_each: int) -> List[Tuple[str, str, str]]:
    items: List[Tuple[str, str, str]] = []

    y = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={yahoo_ticker}&region=US&lang=en-US"
    items += [("Yahoo", t, l) for t, l in _rss_entries(y, limit_each)]

    sa = f"https://seekingalpha.com/symbol/{yahoo_ticker}.xml"
    items += [("SeekingAlpha", t, l) for t, l in _rss_entries(sa, limit_each)]

    q = requests.utils.quote(f"{yahoo_ticker} stock OR {yahoo_ticker} earnings OR {yahoo_ticker} guidance")
    gn = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    items += [("GoogleNews", t, l) for t, l in _rss_entries(gn, limit_each)]

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


# ---------- FMP earnings calendar ----------
def fetch_earnings_calendar(cfg: RadarConfig, from_date: str, to_date: str) -> List[Dict[str, Any]]:
    if not cfg.fmp_api_key:
        return []
    url = "https://financialmodelingprep.com/api/v3/earning_calendar"
    params = {"from": from_date, "to": to_date, "apikey": cfg.fmp_api_key}
    try:
        r = requests.get(url, params=params, timeout=35)
        if r.status_code != 200:
            return []
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def run_weekly_earnings_table(cfg: RadarConfig, now: datetime, st=None) -> Dict[str, Any]:
    """
    Pondělní tabulka earnings pro aktuální týden.
    Rozsah: Po..Ne (7 dní).
    Filtr: jen tickery z našeho univerza (portfolio+watchlist+new_candidates).
    """
    start = now.date()
    end = (now + timedelta(days=7)).date()

    data = fetch_earnings_calendar(cfg, start.isoformat(), end.isoformat())

    # naše tickery (raw->resolved)
    resolved, raw_to_resolved = resolved_universe(cfg, universe=None)
    allowed = set(resolved)
    # některé earnings v FMP vrací symbol bez suffixu; povolíme i raw set
    raw_allowed = set(raw_to_resolved.keys())

    rows: List[Dict[str, Any]] = []
    for r in data:
        sym = str(r.get("symbol") or "").strip().upper()
        if not sym:
            continue

        # match buď přes resolved, nebo raw (z configu)
        if sym not in allowed and sym not in raw_allowed:
            continue

        when = str(r.get("date") or "").strip()
        time = str(r.get("time") or "").strip()  # AMC/BMO/…
        eps_est = r.get("epsEstimated", None)
        rev_est = r.get("revenueEstimated", None)

        # přidej jméno firmy (pokud umíme)
        # - pokud sym je raw, mapneme na resolved
        resolved_sym = sym
        if sym in raw_to_resolved:
            resolved_sym = raw_to_resolved[sym]

        company = resolve_company_name(resolved_sym, st=st)

        rows.append({
            "symbol": sym,
            "resolved": resolved_sym,
            "company": company,
            "date": when,
            "time": time,
            "eps_est": eps_est,
            "rev_est": rev_est,
        })

    # sort: date then time then symbol
    def _key(x):
        return (x.get("date", ""), x.get("time", ""), x.get("symbol", ""))

    rows_sorted = sorted(rows, key=_key)

    return {
        "meta": {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "count": len(rows_sorted),
        },
        "rows": rows_sorted,
    }


# ---------- Public API ----------
def run_radar_snapshot(
    cfg: RadarConfig,
    now: datetime,
    reason: str = "snapshot",
    universe: Optional[List[str]] = None,
    st=None,
) -> Dict[str, Any]:
    resolved, raw_to_resolved = resolved_universe(cfg, universe=universe)
    regime_label, regime_detail, regime_score = market_regime(cfg)

    rows: List[Dict[str, Any]] = []
    for resolved_t in resolved:
        raw = None
        for k, v in raw_to_resolved.items():
            if v == resolved_t:
                raw = k
                break
        raw = raw or resolved_t

        lc = last_close_prev_close(resolved_t)
        pct_1d = None
        if lc:
            last, prev = lc
            pct_1d = pct(last, prev)

        momentum = 0.0 if pct_1d is None else min(10.0, (abs(pct_1d) / 8.0) * 10.0)
        vol_ratio = volume_ratio_1d(resolved_t)
        news = news_combined(resolved_t, int(cfg.news_per_ticker or 2))
        why = why_from_headlines(news)
        catalyst = min(10.0, 1.0 + 0.7 * len(news)) if news else 0.0

        raw_feat = {
            "pct_1d": pct_1d,
            "momentum": momentum,
            "rel_strength": 0.0,
            "vol_ratio": vol_ratio,
            "catalyst_score": catalyst,
            "regime_score": regime_score,
        }

        feats = compute_features(raw_feat)
        score = compute_score(feats, cfg.weights)

        lvl_key, lvl_info = pick_level(
            pct_from_open=None,
            pct_1d=pct_1d,
            vol_ratio=vol_ratio,
            has_catalyst=bool(news),
            score=score,
        )

        company = resolve_company_name(resolved_t, st=st)

        rows.append({
            "ticker": raw,
            "resolved": resolved_t,
            "company": company,
            "pct_1d": pct_1d,
            "class": movement_class(pct_1d),
            "score": float(score),
            "src": "RSS",
            "why": why,
            "news": [{"src": s, "title": t, "url": u} for (s, t, u) in news],
            "market_regime": {"label": regime_label, "detail": regime_detail, "score": regime_score},
            "level_key": lvl_key,
            "level": lvl_info["level_label"],
        })

    rows_sorted = sorted(rows, key=lambda r: r.get("score", 0.0), reverse=True)
    top_n = int(cfg.top_n or 5)
    return {
        "meta": {
            "timestamp": now.strftime("%Y-%m-%d %H:%M"),
            "market_regime": {"label": regime_label, "detail": regime_detail, "score": regime_score},
            "reason": reason,
        },
        "top": rows_sorted[:top_n],
        "worst": list(reversed(rows_sorted[-top_n:])),
        "rows": rows_sorted,
    }


def run_alerts_snapshot(cfg: RadarConfig, now: datetime, st) -> List[Dict[str, Any]]:
    threshold = float(cfg.alert_threshold_pct or 3.0)

    tickers = set()
    for r in (cfg.portfolio or []):
        if isinstance(r, dict) and r.get("ticker"):
            tickers.add(str(r["ticker"]).strip().upper())
    for x in (cfg.watchlist or []):
        tickers.add(str(x).strip().upper())

    alerts: List[Dict[str, Any]] = []
    day = now.strftime("%Y-%m-%d")

    for raw_t in sorted(tickers):
        resolved_t = map_ticker(cfg, raw_t)
        ol = intraday_open_last(resolved_t)
        if not ol:
            continue
        o, last = ol
        ch = pct(last, o)

        if abs(ch) >= threshold:
            key = f"{raw_t}|{round(ch,2)}"
            if st is not None and hasattr(st, "should_alert"):
                if not st.should_alert(raw_t, key, day):
                    continue

            company = resolve_company_name(resolved_t, st=st)

            alerts.append({
                "ticker": raw_t,
                "resolved": resolved_t,
                "company": company,
                "pct_from_open": ch,
                "movement": movement_class(ch),
                "open": o,
                "last": last,
            })

    return sorted(alerts, key=lambda a: abs(float(a.get("pct_from_open", 0.0))), reverse=True)