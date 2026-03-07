import os
import math
import requests
import feedparser

from datetime import datetime, date


# ----------------------------
# helpers
# ----------------------------
def safe_float(x):
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _get_fmp_key(cfg: dict) -> str:
    return (os.getenv("FMPAPIKEY") or os.getenv("FMP_API_KEY") or (cfg.get("fmp_api_key") if isinstance(cfg, dict) else "") or "").strip()


def fmp_get(path: str, cfg: dict, params=None):
    key = _get_fmp_key(cfg)
    if not key:
        return None
    url = f"https://financialmodelingprep.com/api/{path}"
    p = dict(params or {})
    p["apikey"] = key
    try:
        r = requests.get(url, params=p, timeout=25)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def map_ticker_for_yahoo(ticker: str, cfg: dict) -> str:
    """
    V config.yml můžeš mít:
    ticker_map:
      CSG: "CSG.PR"
      SGLD: "SGLD.L"
    """
    ticker = (ticker or "").strip().upper()
    tmap = {}
    if isinstance(cfg, dict):
        tmap = cfg.get("ticker_map") or {}
    if isinstance(tmap, dict):
        mapped = tmap.get(ticker)
        if mapped:
            return str(mapped).strip()
    return ticker


# ----------------------------
# price + volume + returns
# ----------------------------

def get_price_data(ticker: str, cfg: dict) -> dict:
    """Get lightweight price snapshot for a ticker.

    Priority:
      1) Financial Modeling Prep v3/quote (fast, avoids Yahoo rate limits)
      2) Stooq daily close as fallback

    Returns:
      {
        "last": float|None,
        "prev_close": float|None,
        "change_pct": float|None,   # percent, e.g. -1.23
        "open": float|None,
        "src": "fmp"|"stooq"|"none"
      }
    """
    t = (ticker or "").upper().strip()
    if not t:
        return {"last": None, "prev_close": None, "change_pct": None, "open": None, "src": "none"}

    # allow e.g. BABA.NE? but keep original for stooq mapping
    try:
        fmp_cfg = Config(fmp_api_key=cfg.get("fmp_api_key", ""), fmp_base=cfg.get("fmp_base", "https://financialmodelingprep.com/api/"))
        if fmp_cfg.fmp_api_key:
            q = fmp_quote([t], cfg=fmp_cfg).get(t)
            if q:
                last = q.get("price")
                prev = q.get("previousClose")
                chg = q.get("changesPercentage")
                opn = q.get("open")
                def _to_f(x):
                    try:
                        return float(x)
                    except Exception:
                        return None
                return {
                    "last": _to_f(last),
                    "prev_close": _to_f(prev),
                    "change_pct": _to_f(chg),
                    "open": _to_f(opn),
                    "src": "fmp",
                }
    except Exception:
        # fall back to stooq below
        pass

    # Fallback: Stooq daily close (free, but EOD only)
    try:
        symbol = map_ticker_stooq(t)
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        if df.empty:
            return {"last": None, "prev_close": None, "change_pct": None, "open": None, "src": "none"}
        last_close = float(df.iloc[-1]["Close"])
        prev_close = float(df.iloc[-2]["Close"]) if len(df) >= 2 else None
        change_pct = ((last_close - prev_close) / prev_close * 100.0) if prev_close else None
        return {"last": last_close, "prev_close": prev_close, "change_pct": change_pct, "open": None, "src": "stooq"}
    except Exception:
        return {"last": None, "prev_close": None, "change_pct": None, "open": None, "src": "none"}



def volume_spike_ratio(ticker: str, cfg: dict) -> float:
    """
    last volume / avg20 volume
    """
    t = map_ticker_for_yahoo(ticker, cfg)
    try:
        h = yf.Ticker(t).history(period="2mo", interval="1d")
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


def ret_5d_pct(ticker: str, cfg: dict):
    t = map_ticker_for_yahoo(ticker, cfg)
    try:
        h = yf.Ticker(t).history(period="8d", interval="1d")
        if h is None or h.empty:
            return None
        c = h["Close"].dropna()
        if len(c) < 6:
            return None
        c0 = float(c.iloc[-1])
        c5 = float(c.iloc[-6])
        if c5 == 0:
            return None
        return (c0 - c5) / c5 * 100.0
    except Exception:
        return None


def rel_strength_5d_vs_bench(ticker: str, bench: str, cfg: dict):
    rt = ret_5d_pct(ticker, cfg)
    rb = ret_5d_pct(bench, cfg)
    if rt is None or rb is None:
        return None
    return rt - rb


# ----------------------------
# earnings (FMP optional)
# ----------------------------
def next_earnings_days(ticker: str, cfg: dict):
    """
    Vrátí počet dní do earnings (jen pokud FMP klíč existuje a FMP vrátí data).
    """
    t = map_ticker_for_yahoo(ticker, cfg)
    data = fmp_get("v3/earning_calendar", cfg, {"symbol": t})
    if not isinstance(data, list) or not data:
        return None

    today = date.today()
    future = []
    for row in data:
        ds = (row.get("date") or "").strip()
        if not ds:
            continue
        try:
            d = datetime.strptime(ds, "%Y-%m-%d").date()
        except Exception:
            continue
        if d >= today:
            future.append(d)

    if not future:
        return None
    return (min(future) - today).days


# ----------------------------
# news (RSS + FMP optional)
# ----------------------------
def _rss_entries(url: str, limit: int):
    feed = feedparser.parse(url)
    out = []
    for e in (feed.entries or [])[:limit]:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        if title:
            out.append((title, link))
    return out


def _news_fmp(ticker: str, cfg: dict, limit: int):
    t = map_ticker_for_yahoo(ticker, cfg)
    data = fmp_get("v3/stock_news", cfg, {"tickers": t, "limit": limit})
    if not isinstance(data, list):
        return []
    out = []
    for row in data[:limit]:
        title = (row.get("title") or "").strip()
        link = (row.get("url") or "").strip()
        if title:
            out.append(("FMP", title, link))
    return out


def _news_yahoo_rss(ticker: str, cfg: dict, limit: int):
    t = map_ticker_for_yahoo(ticker, cfg)
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"
    return [("Yahoo", tt, ll) for tt, ll in _rss_entries(url, limit)]


def _news_seekingalpha_rss(ticker: str, cfg: dict, limit: int):
    t = map_ticker_for_yahoo(ticker, cfg)
    url = f"https://seekingalpha.com/symbol/{t}.xml"
    return [("SeekingAlpha", tt, ll) for tt, ll in _rss_entries(url, limit)]


def _news_google_rss(ticker: str, cfg: dict, limit: int):
    t = map_ticker_for_yahoo(ticker, cfg)
    q = requests.utils.quote(f"{t} stock OR {t} earnings OR {t} guidance")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return [("GoogleNews", tt, ll) for tt, ll in _rss_entries(url, limit)]


def combined_news(ticker: str, cfg: dict, limit_each: int = 2):
    """
    Vrací list tuple: (src, title, link)
    - deduplikace podle title
    """
    items = []
    items += _news_fmp(ticker, cfg, limit_each)
    items += _news_yahoo_rss(ticker, cfg, limit_each)
    items += _news_seekingalpha_rss(ticker, cfg, limit_each)
    items += _news_google_rss(ticker, cfg, limit_each)

    seen = set()
    uniq = []
    for src, title, link in items:
        key = (title or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append((src, title, link))
    return uniq


# ----------------------------
# market regime (simple)
# ----------------------------
def market_regime(cfg: dict):
    """
    Režim trhu: RISK-ON / RISK-OFF / NEUTRAL (jen Yahoo)
    """
    label = "NEUTRAL"
    detail = []
    try:
        spy = yf.Ticker("SPY").history(period="3mo", interval="1d")
        if spy is not None and not spy.empty:
            close = spy["Close"].dropna()
            if len(close) >= 25:
                c0 = float(close.iloc[-1])
                ma20 = float(close.tail(20).mean())
                trend = ((c0 - ma20) / ma20) * 100.0 if ma20 else 0.0
                detail.append(f"SPY vs MA20: {trend:+.2f}%")
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
                v_ch = ((v_now - v_5) / v_5) * 100.0 if v_5 else 0.0
                detail.append(f"VIX 5D: {v_ch:+.1f}% (aktuálně {v_now:.1f})")
                if v_ch > 10:
                    label = "RISK-OFF"
                elif v_ch < -10 and label != "RISK-OFF":
                    label = "RISK-ON"
    except Exception:
        pass

    return label, "; ".join(detail) if detail else "Bez dostatečných dat."

def fmp_quote(symbols: list[str], cfg: Config) -> dict[str, dict]:
    """Batch quote from Financial Modeling Prep.
    Returns dict[ticker] -> {price, previousClose, changePercent, volume, marketCap, ...}
    Uses v3/quote endpoint which supports comma-separated symbols.
    """
    if not symbols:
        return {}
    # FMP limit: keep request reasonably sized
    out: dict[str, dict] = {}
    chunks = [symbols[i:i+100] for i in range(0, len(symbols), 100)]
    for chunk in chunks:
        path = "v3/quote/" + ",".join(chunk)
        data = fmp_get(path, cfg=cfg)
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(data["error"])
        if not isinstance(data, list):
            continue
        for row in data:
            sym = str(row.get("symbol") or "").upper()
            if not sym:
                continue
            out[sym] = row
    return out


