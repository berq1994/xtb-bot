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
    raw = (t or "").strip().upper()
    tm = getattr(cfg, "ticker_map", None)
    if isinstance(tm, dict):
        return str(tm.get(raw) or raw).strip()
    return raw


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
        if spy is not None and len(spy) >= 30:
            close = spy["Close"]
            ma20 = close.rolling(20).mean().iloc[-1]
            last = float(close.iloc[-1])
            if ma20 and last > ma20:
                detail.append("SPY nad MA20")
                score += 1.0
            else:
                detail.append("SPY pod MA20")
                score -= 1.0
    except Exception:
        detail.append("SPY data n/a")

    try:
        vix = yf.Ticker(vix_t).history(period="1mo", interval="1d")
        if vix is not None and len(vix) >= 10:
            last = float(vix["Close"].iloc[-1])
            if last >= 22:
                detail.append(f"VIX vysoký ({last:.1f})")
                score -= 1.5
            elif last <= 16:
                detail.append(f"VIX nízký ({last:.1f})")
                score += 1.0
            else:
                detail.append(f"VIX střed ({last:.1f})")
    except Exception:
        detail.append("VIX data n/a")

    if score >= 6.5:
        label = "RISK-ON"
    elif score <= 4.0:
        label = "RISK-OFF"

    return label, "; ".join(detail), float(score)


def last_close_prev_close(ticker: str) -> Optional[Tuple[float, float]]:
    try:
        h = yf.Ticker(ticker).history(period="5d", interval="1d")
        if h is None or len(h) < 2:
            return None
        last = float(h["Close"].iloc[-1])
        prev = float(h["Close"].iloc[-2])
        return last, prev
    except Exception:
        return None


def intraday_open_last(ticker: str) -> Optional[Tuple[float, float]]:
    try:
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h is None or len(h) < 3:
            return None
        o = float(h["Open"].iloc[0])
        last = float(h["Close"].iloc[-1])
        return o, last
    except Exception:
        return None


def volume_ratio_1d(ticker: str) -> float:
    try:
        h = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if h is None or len(h) < 10:
            return 1.0
        vol = h["Volume"]
        last = float(vol.iloc[-1])
        avg20 = float(vol.rolling(20).mean().iloc[-1]) if len(vol) >= 20 else float(vol.mean())
        if avg20 <= 0:
            return 1.0
        return last / avg20
    except Exception:
        return 1.0


def resolve_company_name(resolved_ticker: str, st=None) -> str:
    if st is not None:
        try:
            nm = st.get_name(resolved_ticker)
            if nm:
                return nm
        except Exception:
            pass

    name = resolved_ticker
    try:
        info = yf.Ticker(resolved_ticker).info or {}
        name = (info.get("shortName") or info.get("longName") or resolved_ticker).strip()
    except Exception:
        name = resolved_ticker

    if st is not None:
        try:
            st.set_name(resolved_ticker, name)
        except Exception:
            pass
    return name


# ---------- News (RSS) ----------
def _rss_entries(url: str, limit: int = 30) -> List[Dict[str, Any]]:
    try:
        d = feedparser.parse(url)
        out = []
        for e in (d.entries or [])[:limit]:
            out.append(
                {
                    "title": getattr(e, "title", ""),
                    "link": getattr(e, "link", ""),
                    "summary": getattr(e, "summary", ""),
                    "published": getattr(e, "published", ""),
                    "published_parsed": getattr(e, "published_parsed", None),
                    "source": getattr(getattr(e, "source", None), "title", "") if getattr(e, "source", None) else "",
                    "publisher": getattr(getattr(d, "feed", None), "title", "") if getattr(d, "feed", None) else "",
                }
            )
        return out
    except Exception:
        return []


def news_combined(resolved_ticker: str, n: int = 2) -> List[Tuple[str, str, str]]:
    items: List[Tuple[str, str, str]] = []
    try:
        rss = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={resolved_ticker}&region=US&lang=en-US"
        for e in _rss_entries(rss, limit=10):
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            if title and link:
                src = (e.get("publisher") or "Yahoo").strip()
                items.append((src, title, link))
            if len(items) >= n:
                break
    except Exception:
        pass
    return items[:n]


def why_from_headlines(news: List[Tuple[str, str, str]]) -> str:
    if not news:
        return "Bez jasného headline katalyzátoru (může být sentiment/technika/flow)."
    title = news[0][1]
    low = title.lower()
    if "earnings" in low or "guidance" in low or "revenue" in low:
        return "Earnings / guidance headline."
    if "downgrade" in low or "upgrade" in low or "price target" in low:
        return "Analyst rating / PT změna."
    if "sec" in low or "lawsuit" in low or "investigation" in low:
        return "Regulace / lawsuit / vyšetřování."
    if "acquire" in low or "merger" in low:
        return "M&A / akvizice."
    if "contract" in low or "deal" in low:
        return "Kontrakt / deal."
    return "Zprávy naznačují katalyzátor – otevři headline a ověř kontext."


# ---------- Geopolitics + learning (ponechano jak mas) ----------
# (tvoje GEO_BASE_KEYWORDS + geopolitics_digest + learn_geopolitics_keywords zustavaji beze zmen)
# ... tady nech presne to, co mas - je to OK ...


# ---------- Earnings ----------
def fetch_earnings_calendar(cfg: RadarConfig, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    key = (cfg.fmp_api_key or "").strip()
    if not key:
        return []
    url = "https://financialmodelingprep.com/api/v3/earning_calendar"
    params = {"from": start.strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d"), "apikey": key}
    try:
        r = requests.get(url, params=params, timeout=25)
        if r.status_code != 200:
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        return data
    except Exception:
        return []


def run_weekly_earnings_table(cfg: RadarConfig, now: datetime, st=None) -> Dict[str, Any]:
    start = now.date()
    end = (now + timedelta(days=7)).date()

    cal = fetch_earnings_calendar(cfg, datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time()))
    uni, _ = resolved_universe(cfg, universe=None)

    rows = []
    for e in cal:
        sym = (e.get("symbol") or "").upper().strip()
        if not sym or sym not in uni:
            continue
        rows.append(
            {
                "date": e.get("date", ""),
                "time": e.get("time", ""),
                "symbol": sym,
                "company": resolve_company_name(map_ticker(cfg, sym), st=st),
                "eps_est": e.get("epsEstimated", ""),
                "rev_est": e.get("revenueEstimated", ""),
            }
        )
    rows.sort(key=lambda x: (x.get("date", ""), x.get("time", ""), x.get("symbol", "")))
    return {"meta": {"from": str(start), "to": str(end)}, "rows": rows}


# ---------- Snapshot ----------
def run_radar_snapshot(cfg: RadarConfig, now: datetime, reason: str, universe: Optional[List[str]] = None, st=None) -> Dict[str, Any]:
    if universe is None:
        uni, _ = resolved_universe(cfg, universe=None)
    else:
        uni, _ = resolved_universe(cfg, universe=universe)

    reg_label, reg_detail, reg_score = market_regime(cfg)

    rows = []
    for raw in uni:
        rt = map_ticker(cfg, raw)
        name = resolve_company_name(rt, st=st)

        lc = last_close_prev_close(rt)
        if lc:
            last, prev = lc
            p1d = pct(last, prev) if prev else None
        else:
            p1d = None

        volr = volume_ratio_1d(rt)
        news = news_combined(rt, int(cfg.news_per_ticker or 2))
        why = why_from_headlines(news)

        feats = compute_features(rt)
        score, parts = compute_score(cfg, feats, p1d, volr, bool(news), reg_label, reg_score)
        lvl = pick_level(score, movement_class(p1d or 0.0, volr))

        rows.append(
            {
                "ticker": raw,
                "resolved": rt,
                "company": name,
                "pct_1d": p1d,
                "vol_ratio": volr,
                "score": score,
                "score_parts": parts,
                "why": why,
                "level": lvl,
            }
        )

    rows.sort(key=lambda r: float(r.get("score", 0.0)), reverse=True)
    top = rows[: int(cfg.top_n or 5)]
    worst = list(reversed(rows[-int(cfg.top_n or 5):]))

    return {
        "meta": {
            "timestamp": now.strftime("%Y-%m-%d %H:%M"),
            "reason": reason,
            "market_regime": {"label": reg_label, "detail": reg_detail, "score": reg_score},
        },
        "top": top,
        "worst": worst,
        "rows": rows,
    }


# ---------- Alerts ----------
def run_alerts_snapshot(cfg: RadarConfig, now: datetime, st=None) -> List[Dict[str, Any]]:
    uni, _ = resolved_universe(cfg, universe=None)
    day = now.strftime("%Y-%m-%d")
    out: List[Dict[str, Any]] = []

    try:
        if st is not None:
            st.cleanup_alert_state(day)
    except Exception:
        pass

    thr = float(cfg.alert_threshold_pct or 3.0)

    for raw in uni:
        rt = map_ticker(cfg, raw)
        name = resolve_company_name(rt, st=st)
        ol = intraday_open_last(rt)
        if not ol:
            continue
        o, last = ol
        if not o:
            continue
        ch = pct(last, o)
        if abs(ch) < thr:
            continue

        key = f"{int(round(ch))}"
        ok = True
        if st is not None:
            try:
                ok = st.should_alert(raw, key, day)
            except Exception:
                ok = True
        if not ok:
            continue

        out.append(
            {
                "ticker": raw,
                "resolved": rt,
                "company": name,
                "pct_from_open": ch,
                "open": o,
                "last": last,
            }
        )

    out.sort(key=lambda x: abs(float(x.get("pct_from_open", 0.0))), reverse=True)
    return out