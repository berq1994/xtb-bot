import requests
import feedparser
import yfinance as yf
from typing import Any, Dict, List, Optional, Tuple

from radar.config import RadarConfig


def fmp_get(cfg: RadarConfig, path: str, params: Optional[Dict[str, Any]] = None):
    if not cfg.fmp_api_key:
        return None
    url = f"https://financialmodelingprep.com/api/{path}"
    p = dict(params or {})
    p["apikey"] = cfg.fmp_api_key
    try:
        r = requests.get(url, params=p, timeout=25)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def daily_last_prev(cfg: RadarConfig, ticker: str) -> Tuple[Optional[float], Optional[float], str]:
    # FMP first
    data = fmp_get(cfg, "v3/historical-price-full/" + ticker, {"serietype": "line", "timeseries": 5})
    if isinstance(data, dict):
        hist = data.get("historical")
        if isinstance(hist, list) and len(hist) >= 2:
            c0 = hist[0].get("close")
            c1 = hist[1].get("close")
            try:
                c0 = float(c0)
                c1 = float(c1)
                return c0, c1, "FMP"
            except Exception:
                pass

    # Yahoo fallback
    try:
        h = yf.Ticker(ticker).history(period="10d", interval="1d")
        if h is None or h.empty:
            return None, None, "—"
        closes = h["Close"].dropna()
        if len(closes) < 2:
            return None, None, "—"
        return float(closes.iloc[-1]), float(closes.iloc[-2]), "Yahoo"
    except Exception:
        return None, None, "—"


def intraday_open_last_yahoo(ticker: str) -> Optional[Tuple[float, float]]:
    try:
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h is None or h.empty:
            return None
        o = float(h["Open"].iloc[0])
        last = float(h["Close"].iloc[-1])
        return o, last
    except Exception:
        return None


def volume_ratio_yahoo(ticker: str) -> float:
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


def ret_5d_yahoo(ticker: str) -> Optional[float]:
    try:
        h = yf.Ticker(ticker).history(period="8d", interval="1d")
        if h is None or h.empty:
            return None
        c = h["Close"].dropna()
        if len(c) < 6:
            return None
        return (float(c.iloc[-1]) - float(c.iloc[-6])) / float(c.iloc[-6]) * 100.0
    except Exception:
        return None


def rel_strength_5d(ticker: str, bench: str) -> Optional[float]:
    r_t = ret_5d_yahoo(ticker)
    r_b = ret_5d_yahoo(bench)
    if r_t is None or r_b is None:
        return None
    return r_t - r_b


def rss_entries(url: str, limit: int):
    feed = feedparser.parse(url)
    out = []
    for e in (feed.entries or [])[:limit]:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        if title:
            out.append((title, link))
    return out


def news_fmp(cfg: RadarConfig, ticker: str, limit: int):
    data = fmp_get(cfg, "v3/stock_news", {"tickers": ticker, "limit": limit})
    if not isinstance(data, list):
        return []
    out = []
    for row in data[:limit]:
        title = (row.get("title") or "").strip()
        link = (row.get("url") or "").strip()
        if title:
            out.append(("FMP", title, link))
    return out


def news_yahoo_rss(ticker: str, limit: int):
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    return [("Yahoo", t, l) for t, l in rss_entries(url, limit)]


def news_seekingalpha_rss(ticker: str, limit: int):
    url = f"https://seekingalpha.com/symbol/{ticker}.xml"
    return [("SeekingAlpha", t, l) for t, l in rss_entries(url, limit)]


def news_google_rss(ticker: str, limit: int):
    q = requests.utils.quote(f"{ticker} stock OR {ticker} earnings OR {ticker} guidance")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return [("GoogleNews", t, l) for t, l in rss_entries(url, limit)]


def combined_news(cfg: RadarConfig, ticker: str, limit_each: int):
    items = []
    items += news_fmp(cfg, ticker, limit_each)
    items += news_yahoo_rss(ticker, limit_each)
    items += news_seekingalpha_rss(ticker, limit_each)
    items += news_google_rss(ticker, limit_each)

    seen = set()
    uniq = []
    for src, title, link in items:
        key = title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((src, title, link))
    return uniq