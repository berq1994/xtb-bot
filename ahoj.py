import os
import re
import json
import math
import time
import yaml
import requests
import feedparser
import yfinance as yf

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# PŘEKLADY (vše do češtiny) – bezpečný fallback
# ============================================================
def _translator():
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="auto", target="cs")
    except Exception:
        return None

_TRANSLATOR = _translator()
_TRANSLATE_CACHE = {}

def cz(text: str) -> str:
    """Přeloží text do češtiny. Když překladač není dostupný, vrátí originál."""
    if not text:
        return ""
    key = text.strip()
    if len(key) < 5:
        return key
    if key in _TRANSLATE_CACHE:
        return _TRANATE_CACHE[key]  # noqa (typo protection)
    if _TRANSLATOR is None:
        _TRANSLATE_CACHE[key] = key
        return key
    try:
        out = _TRANSLATOR.translate(key)
        _TRANSLATE_CACHE[key] = out
        return out
    except Exception:
        _TRANSLATE_CACHE[key] = key
        return key


# ============================================================
# STATE (cache přes GitHub Actions)
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

LAST_RUN_FILE = os.path.join(STATE_DIR, "last_run.json")
PROFILE_CACHE_FILE = os.path.join(STATE_DIR, "profiles.json")
SNAPSHOTS_FILE = os.path.join(STATE_DIR, "portfolio_snapshots.json")
ALERTS_STATE_FILE = os.path.join(STATE_DIR, "alerts_state.json")
STUDIES_STATE_FILE = os.path.join(STATE_DIR, "studies_state.json")


# ============================================================
# UTIL
# ============================================================
def read_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_float(x):
    try:
        if x is None:
            return None
        x = float(x)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None

def pct_change(new, old):
    if new is None or old is None or old == 0:
        return None
    return ((new - old) / old) * 100.0

def clamp(x, lo=0.0, hi=10.0):
    return max(lo, min(hi, x))

def bar(pct: float, width: int = 14) -> str:
    """Textový bar pro +/- 0..10 %."""
    if pct is None:
        return ""
    a = min(abs(pct), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)

def chunk_text(text: str, limit: int = 3500):
    parts, buf = [], ""
    for line in text.splitlines(True):
        if len(buf) + len(line) > limit:
            parts.append(buf)
            buf = ""
        buf += line
    if buf.strip():
        parts.append(buf)
    return parts

def uniq_keep_order(seq):
    seen = set()
    out = []
    for x in seq:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


# ============================================================
# CONFIG LOADER (supports ${ENV_VAR})
# ============================================================
ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

def _expand_env_in_obj(obj):
    if isinstance(obj, dict):
        return {k: _expand_env_in_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_in_obj(v) for v in obj]
    if isinstance(obj, str):
        def repl(m):
            key = m.group(1)
            return os.getenv(key, "")
        return ENV_PATTERN.sub(repl, obj)
    return obj

def load_config(path="config.yml"):
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    cfg = _expand_env_in_obj(raw or {})
    return cfg


# ============================================================
# TELEGRAM
# ============================================================
def telegram_send(bot_token: str, chat_id: str, text: str):
    if not bot_token or not chat_id:
        print("⚠️ Telegram není nastaven (chybí token/chat_id).")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, data={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        }, timeout=35)
        if r.status_code != 200:
            print("Telegram error:", r.status_code, r.text[:500])
    except Exception as e:
        print("Telegram exception:", repr(e))

def telegram_send_long(bot_token: str, chat_id: str, text: str):
    for part in chunk_text(text):
        telegram_send(bot_token, chat_id, part)


# ============================================================
# FMP API
# ============================================================
def fmp_get(api_key: str, path: str, params=None):
    if not api_key:
        return None
    url = f"https://financialmodelingprep.com/api/{path}"
    p = dict(params or {})
    p["apikey"] = api_key
    try:
        r = requests.get(url, params=p, timeout=25)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


# ============================================================
# PORTFOLIO MODEL
# ============================================================
@dataclass
class Lot:
    qty: float
    entry: float
    currency: str
    broker: str
    note: str = ""

@dataclass
class Position:
    ticker: str
    lots: list

    def total_qty(self) -> float:
        return float(sum(l.qty for l in self.lots))

    def avg_entry(self) -> float:
        # vážený průměr; pokud chybí entry (0/None), ignoruj v průměru
        num = 0.0
        den = 0.0
        for l in self.lots:
            if l.entry and l.entry > 0:
                num += l.qty * l.entry
                den += l.qty
        return (num / den) if den > 0 else 0.0

    def currencies(self):
        return uniq_keep_order([l.currency for l in self.lots])


def parse_positions(cfg) -> list:
    positions = []
    for p in (cfg.get("portfolio") or []):
        t = (p.get("ticker") or "").strip().upper()
        lots = []
        for row in (p.get("lots") or []):
            lots.append(Lot(
                qty=float(row.get("qty") or 0),
                entry=float(row.get("entry") or 0),
                currency=(row.get("currency") or "").strip().upper(),
                broker=(row.get("broker") or "").strip(),
                note=(row.get("note") or "").strip()
            ))
        if t and lots:
            positions.append(Position(ticker=t, lots=lots))
    return positions


# ============================================================
# PROFILES (FMP primárně, Yahoo fallback) + CACHE
# ============================================================
def profiles_cache_load():
    return read_json(PROFILE_CACHE_FILE, {})

def profiles_cache_save(cache):
    write_json(PROFILE_CACHE_FILE, cache)

def get_profile(api_key: str, ticker: str):
    cache = profiles_cache_load()
    if ticker in cache:
        return cache[ticker]

    prof = {"name": ticker, "sector": "", "industry": "", "description": ""}

    data = fmp_get(api_key, "v3/profile", {"symbol": ticker})
    if isinstance(data, list) and data:
        row = data[0]
        prof["name"] = (row.get("companyName") or ticker).strip()
        prof["sector"] = (row.get("sector") or "").strip()
        prof["industry"] = (row.get("industry") or "").strip()
        prof["description"] = (row.get("description") or "").strip()

    if prof["name"] == ticker:
        try:
            info = yf.Ticker(ticker).info or {}
            prof["name"] = (info.get("longName") or info.get("shortName") or ticker).strip()
            prof["sector"] = prof["sector"] or (info.get("sector") or "").strip()
            prof["industry"] = prof["industry"] or (info.get("industry") or "").strip()
            prof["description"] = prof["description"] or (info.get("longBusinessSummary") or "").strip()
        except Exception:
            pass

    cache[ticker] = prof
    profiles_cache_save(cache)
    return prof


# ============================================================
# PRICES (daily close/prev close) + INTRADAY open/last + VOLUME SPIKE
# ============================================================
def prices_daily_yahoo(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="10d", interval="1d")
        if h is None or h.empty:
            return None
        closes = h["Close"].dropna()
        if len(closes) < 2:
            return None
        return float(closes.iloc[-1]), float(closes.iloc[-2])
    except Exception:
        return None

def intraday_open_last_yahoo(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h is None or h.empty:
            return None
        o = safe_float(h["Open"].iloc[0])
        last = safe_float(h["Close"].iloc[-1])
        if o is None or last is None:
            return None
        return o, last
    except Exception:
        return None

def volume_spike_yahoo(ticker: str):
    """Poměr objemu posledního dne vs průměr 20 dní (1.0 = normál)."""
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


# ============================================================
# NEWS (FMP + RSS)
# ============================================================
def rss_entries(url: str, limit: int):
    feed = feedparser.parse(url)
    out = []
    for e in (feed.entries or [])[:limit]:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        if title:
            out.append((title, link))
    return out

def news_fmp(api_key: str, ticker: str, limit: int):
    data = fmp_get(api_key, "v3/stock_news", {"tickers": ticker, "limit": limit})
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

def combined_news(api_key: str, ticker: str, limit_each: int):
    items = []
    items += news_fmp(api_key, ticker, limit_each)
    items += news_yahoo_rss(ticker, limit_each)
    items += news_seekingalpha_rss(ticker, limit_each)
    items += news_google_rss(ticker, limit_each)

    # dedupe podle titulku
    seen = set()
    uniq = []
    for src, title, link in items:
        key = title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
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

def why_from_headlines(news_items):
    if not news_items:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    titles = " ".join([t for (_, t, _) in news_items]).lower()
    hits = []
    for keys, reason in WHY_KEYWORDS:
        if any(k in titles for k in keys):
            hits.append(reason)
    if not hits:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    return "; ".join(hits[:2]) + "."


# ============================================================
# EARNINGS (FMP earning_calendar)
# ============================================================
def fmp_next_earnings_date(api_key: str, ticker: str):
    data = fmp_get(api_key, "v3/earning_calendar", {"symbol": ticker})
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
    return min(future) if future else None

def days_to_earnings(api_key: str, ticker: str):
    ed = fmp_next_earnings_date(api_key, ticker)
    if not ed:
        return None
    return (ed - date.today()).days

def earnings_note(days_away):
    if days_away is None:
        return ""
    if days_away <= 2:
        return "⚠️ Earnings do 48h: vyšší riziko gapu."
    if days_away <= 7:
        return "⚠️ Earnings do týdne: vyšší volatilita."
    if days_away <= 14:
        return "ℹ️ Earnings do 2 týdnů."
    return ""


# ============================================================
# MARKET REGIME (SPY trend + VIX change)
# ============================================================
def market_regime(spy_ticker="SPY", vix_ticker="^VIX"):
    label = "NEUTRÁLNÍ"
    detail = []
    try:
        spy = yf.Ticker(spy_ticker).history(period="3mo", interval="1d")
        if spy is not None and not spy.empty:
            close = spy["Close"].dropna()
            if len(close) >= 25:
                c0 = float(close.iloc[-1])
                ma20 = float(close.tail(20).mean())
                trend = (c0 - ma20) / ma20 * 100.0
                detail.append(f"SPY vs MA20: {trend:+.2f}%")
                if trend > 0.7:
                    label = "RISK-ON"
                elif trend < -0.7:
                    label = "RISK-OFF"

        vix = yf.Ticker(vix_ticker).history(period="1mo", interval="1d")
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

    return label, "; ".join(detail) if detail else "Bez dostatečných dat (fallback režim)."


# ============================================================
# RETURNS / MOMENTUM / RELATIVE STRENGTH
# ============================================================
def ret_nd(ticker: str, days: int):
    try:
        h = yf.Ticker(ticker).history(period=f"{max(days+3, 8)}d", interval="1d")
        if h is None or h.empty:
            return None
        c = h["Close"].dropna()
        if len(c) < (days + 1):
            return None
        old = float(c.iloc[-(days+1)])
        new = float(c.iloc[-1])
        return (new - old) / old * 100.0
    except Exception:
        return None

def rel_strength_5d(ticker: str, spy: str = "SPY"):
    r_t = ret_nd(ticker, 5)
    r_s = ret_nd(spy, 5)
    if r_t is None or r_s is None:
        return None
    return r_t - r_s


# ============================================================
# SCORE ENGINE (tvůj “PRO verze” styl)
# ============================================================
def earnings_score(days_away):
    if days_away is None:
        return 0.0
    if days_away <= 2:
        return 3.0
    if days_away <= 7:
        return 2.0
    if days_away <= 14:
        return 1.0
    return 0.0

def rs_score(rs):
    # RS diff vs SPY: +0..+5 -> +0..3, -5..0 -> -0..-3
    if rs is None:
        return 0.0
    return clamp((rs / 5.0) * 3.0, -3.0, 3.0)

def momentum_score(r1, r5, r20):
    # jednoduché škálování: 1D/5D/20D dohromady, limit -5..+5
    vals = [v for v in [r1, r5, r20] if v is not None]
    if not vals:
        return 0.0
    s = sum(vals) / len(vals)
    return clamp((s / 10.0) * 5.0, -5.0, 5.0)

def volvol_score(vol_spike):
    # 1.0 normál; 2.0 = výrazný spike
    if vol_spike is None:
        return 0.0
    return clamp((vol_spike - 1.0) * 2.0, 0.0, 3.0)

def catalyst_score(news_items):
    # jednoduchá heuristika: když je hodně headlineů, lehce +; když nic, 0
    n = len(news_items or [])
    if n <= 0:
        return 0.0
    if n == 1:
        return 0.5
    if n == 2:
        return 1.0
    return 1.5

def regime_score(label):
    if label == "RISK-ON":
        return 1.0
    if label == "RISK-OFF":
        return -1.0
    return 0.0

def compute_score(cfg, ticker: str, regime_label: str, spy: str):
    w = cfg.get("weights") or {}
    r1 = ret_nd(ticker, 1)
    r5 = ret_nd(ticker, 5)
    r20 = ret_nd(ticker, 20)
    rs = rel_strength_5d(ticker, spy)
    vol_spike = volume_spike_yahoo(ticker)
    news_items = combined_news(cfg.get("fmp_api_key",""), ticker, int((cfg.get("news") or {}).get("per_ticker", 2)))
    days_earn = days_to_earnings(cfg.get("fmp_api_key",""), ticker) if cfg.get("fmp_api_key") else None

    s_mom = momentum_score(r1, r5, r20)
    s_rs = rs_score(rs)
    s_vv = volvol_score(vol_spike)
    s_cat = catalyst_score(news_items)
    s_reg = regime_score(regime_label)
    s_earn = earnings_score(days_earn)

    # vážený mix (0..100-ish -> znormalizujeme do -10..+10)
    score = (
        w.get("momentum", 0.25) * s_mom +
        w.get("rel_strength", 0.20) * s_rs +
        w.get("volatility_volume", 0.15) * s_vv +
        w.get("catalyst", 0.20) * s_cat +
        w.get("market_regime", 0.20) * s_reg
    )

    # earnings penalizace pro “WAIT”
    wait = False
    risk_rules = cfg.get("risk_rules") or {}
    wait_hours = int(risk_rules.get("earnings_wait_hours", 48))
    if days_earn is not None and days_earn <= 2 and wait_hours >= 48:
        wait = True
        score -= 1.0  # lehký downweight, protože gap risk

    return {
        "ticker": ticker,
        "r1": r1, "r5": r5, "r20": r20,
        "rs5": rs,
        "vol_spike": vol_spike,
        "days_to_earnings": days_earn,
        "earn_note": earnings_note(days_earn),
        "news": news_items[:4],
        "why": why_from_headlines(news_items[:6]),
        "score": float(score),
        "wait": wait
    }


# ============================================================
# STUDIES (lehké “učící se” – stahuje poslední studie přes arXiv RSS)
# Pozn: ukládá jen metadata + “pravidlo”, ne texty.
# ============================================================
def arxiv_rss(query: str, limit: int = 5):
    q = requests.utils.quote(query)
    url = f"https://export.arxiv.org/rss/{q}"
    feed = feedparser.parse(url)
    out = []
    for e in (feed.entries or [])[:limit]:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        summary = (getattr(e, "summary", "") or "").strip()
        if title:
            out.append({"title": title, "link": link, "summary": summary[:500]})
    return out

def studies_update():
    state = read_json(STUDIES_STATE_FILE, {"seen": [], "items": []})
    seen = set(state.get("seen") or [])
    items = state.get("items") or []

    # dotazy: trading/momentum/risk management
    queries = [
        "q-fin.TR",
        "momentum trading",
        "volatility forecasting",
        "portfolio risk management",
    ]

    new_items = []
    for q in queries:
        try:
            for it in arxiv_rss(q, limit=5):
                key = it["title"].lower().strip()
                if key in seen:
                    continue
                seen.add(key)
                new_items.append(it)
        except Exception:
            continue

    # udržuj rozumnou velikost
    items = (new_items + items)[:30]
    write_json(STUDIES_STATE_FILE, {"seen": list(seen)[-300:], "items": items})
    return new_items


# ============================================================
# SNAPSHOTS (portfolio value per ticker - close) – pro historii
# ============================================================
def snapshot_store(cfg, positions, spy="SPY"):
    max_snap = int(cfg.get("max_portfolio_snapshots", 200))
    snaps = read_json(SNAPSHOTS_FILE, [])
    ts = datetime.utcnow().isoformat() + "Z"

    tickers = uniq_keep_order([p.ticker for p in positions] + [spy])
    rows = {}
    for t in tickers:
        lp = prices_daily_yahoo(t)
        if lp:
            last, prev = lp
            rows[t] = {"last": last, "prev": prev, "ch_pct": pct_change(last, prev)}
        else:
            rows[t] = {"last": None, "prev": None, "ch_pct": None}

    snaps.insert(0, {"ts": ts, "rows": rows})
    snaps = snaps[:max_snap]
    write_json(SNAPSHOTS_FILE, snaps)


# ============================================================
# REPORT BUILDERS
# ============================================================
def fmt_pct(x):
    return "—" if x is None else f"{x:+.2f}%"

def format_ticker_line(item):
    ch = item.get("r1")
    score = item.get("score")
    rs5 = item.get("rs5")
    vv = item.get("vol_spike")
    earn = item.get("earn_note","")
    wait = "⏳WAIT" if item.get("wait") else ""
    return (
        f"{item['ticker']}: 1D {fmt_pct(ch)} | RS5 {fmt_pct(rs5)} | "
        f"Vol× {vv:.2f} | Score {score:+.2f} {wait} {earn}".strip()
    )

def trade_plan(cfg, item):
    # invalidace: default -2 až -4% dle configu
    rr = cfg.get("risk_rules") or {}
    inv = rr.get("swing_invalidation_pct", [-2, -4])
    inv_txt = f"{inv[0]}% až {inv[1]}% (dle volatility)"

    mode = (cfg.get("advice_mode") or "SOFT").upper()
    action = "SETUP"
    if mode == "HARD":
        if item["wait"]:
            action = "WAIT / MENŠÍ POZICE"
        else:
            # hrubé práh
            if item["score"] >= 1.5:
                action = "BUY"
            elif item["score"] <= -1.5:
                action = "SELL/REDUCE"
            else:
                action = "HOLD"

    lines = [
        f"Akce: {action}",
        f"Proč: momentum(1D/5D/20D), RS vs SPY, objem, katalyzátory, režim trhu",
        f"Rizika: earnings, makro, volatilita, gap bez zpráv",
        f"Plan: vstupní zóna = dle limitu/rozptylu; invalidace = {inv_txt}; cíl = postupné odprodeje / trailing",
        f"Confidence: {min(5, max(1, int(round(abs(item['score'])+1))))}/5",
    ]
    return "\n".join(lines)

def report_radar(cfg, positions, watchlist, candidates):
    spy = (cfg.get("benchmarks") or {}).get("spy","SPY")
    vix = (cfg.get("benchmarks") or {}).get("vix","^VIX")

    regime_label, regime_detail = market_regime(spy, vix)

    # univerzum pro radar
    tickers = uniq_keep_order([p.ticker for p in positions] + (watchlist or []))
    results = []
    for t in tickers:
        results.append(compute_score(cfg, t, regime_label, spy))

    # top movers (1D)
    movers = sorted([r for r in results if r["r1"] is not None], key=lambda x: abs(x["r1"]), reverse=True)[:8]
    top_buy = sorted(results, key=lambda x: x["score"], reverse=True)[:8]
    top_sell = sorted(results, key=lambda x: x["score"])[:8]

    # opportunities from candidates
    opps = []
    held = set([p.ticker for p in positions])
    wl = set([x.upper() for x in (watchlist or [])])
    for t in (candidates or []):
        t = t.upper()
        if t in held or t in wl:
            continue
        opps.append(compute_score(cfg, t, regime_label, spy))
    opps = sorted(opps, key=lambda x: x["score"], reverse=True)[:5]

    lines = []
    lines.append("📡 MEGA INVESTIČNÍ RADAR (CZ)")
    lines.append(f"🧭 Režim trhu: {regime_label} | {regime_detail}")
    lines.append("")
    lines.append("⚡ TOP pohyby (1D):")
    for r in movers:
        lines.append("  • " + format_ticker_line(r))

    lines.append("")
    lines.append("🟢 TOP kandidáti (BUY/SETUP):")
    for r in top_buy[:6]:
        lines.append("  • " + format_ticker_line(r))

    lines.append("")
    lines.append("🔴 TOP kandidáti (SELL/REDUCE):")
    for r in top_sell[:6]:
        lines.append("  • " + format_ticker_line(r))

    if opps:
        lines.append("")
        lines.append("🧪 NOVÉ NADĚJNÉ (mimo portfolio):")
        for r in opps:
            lines.append("  • " + format_ticker_line(r))

    lines.append("")
    lines.append("📌 Pozn.: /plan TICKER = trade plan, /why TICKER = proč se hýbe, /risk TICKER = rizika (v této verzi posíláme přes scheduled reporty).")
    return "\n".join(lines), results, regime_label

def report_positions(cfg, positions):
    lines = []
    lines.append("📦 PORTFOLIO – kontrola vstupů (z config.yml)")
    for p in positions:
        avg = p.avg_entry()
        lots_txt = ", ".join([f"{l.qty:g}@{l.entry:g}{l.currency}({l.broker})" for l in p.lots])
        lines.append(f"• {p.ticker}: qty {p.total_qty():g} | avg {avg:g} | lots: {lots_txt}")
    return "\n".join(lines)


# ============================================================
# ALERTS (intraday % od OPEN) + anti-spam
# ============================================================
def alerts_run(cfg, positions):
    alerts_cfg = cfg.get("alerts") or {}
    if not bool(alerts_cfg.get("enabled", True)):
        return None

    start = (alerts_cfg.get("window_start") or "12:00").strip()
    end = (alerts_cfg.get("window_end") or "21:00").strip()
    thr = float(alerts_cfg.get("threshold_pct_from_open") or 3.0)

    tz = ZoneInfo((cfg.get("timezone") or "Europe/Prague").strip())
    now = datetime.now(tz)
    hm = now.strftime("%H:%M")
    if not (start <= hm <= end):
        return None

    state = read_json(ALERTS_STATE_FILE, {"sent": {}})
    sent = state.get("sent") or {}

    lines = []
    for p in positions:
        got = intraday_open_last_yahoo(p.ticker)
        if not got:
            continue
        o, last = got
        ch = pct_change(last, o)
        if ch is None:
            continue
        if abs(ch) >= thr:
            key = f"{p.ticker}:{now.strftime('%Y-%m-%d')}"
            # pošli max 1 alert/den/ticker
            if sent.get(key):
                continue
            sent[key] = {"at": now.isoformat(), "ch": ch}
            lines.append(f"🚨 ALERT {p.ticker}: {ch:+.2f}% od dnešního OPEN (limit {thr:.1f}%)")

    if lines:
        write_json(ALERTS_STATE_FILE, {"sent": sent})
        return "\n".join(lines)
    return None


# ============================================================
# MAIN
# ============================================================
def main():
    cfg = load_config("config.yml")

    bot_token = (cfg.get("telegram") or {}).get("bot_token","").strip()
    chat_id = str((cfg.get("telegram") or {}).get("chat_id","")).strip()

    tz = ZoneInfo((cfg.get("timezone") or "Europe/Prague").strip())

    positions = parse_positions(cfg)
    watchlist = [x.upper() for x in (cfg.get("watchlist") or [])]
    candidates = [x.upper() for x in (cfg.get("new_candidates") or [])]

    mode = (os.getenv("RUN_MODE") or "radar").strip().lower()
    # supported: radar | positions | alerts | studies
    # (GitHub Actions spouští různé RUN_MODE podle schedule)

    if mode == "positions":
        text = report_positions(cfg, positions)
        telegram_send_long(bot_token, chat_id, text)
        return

    if mode == "studies":
        new_items = studies_update()
        if not new_items:
            telegram_send(bot_token, chat_id, "📚 Studie: žádné nové položky od minula.")
            return
        lines = ["📚 Nové studie (arXiv/RSS) – rychlý výběr:"]
        for it in new_items[:6]:
            lines.append(f"• {cz(it['title'])}\n  {it['link']}")
        telegram_send_long(bot_token, chat_id, "\n".join(lines))
        return

    if mode == "alerts":
        msg = alerts_run(cfg, positions)
        if msg:
            telegram_send_long(bot_token, chat_id, msg)
        else:
            print("No alerts / outside window / already sent.")
        return

    # default: radar
    radar_text, results, regime = report_radar(cfg, positions, watchlist, candidates)

    # store snapshot
    try:
        snapshot_store(cfg, positions, spy=(cfg.get("benchmarks") or {}).get("spy","SPY"))
    except Exception as e:
        print("Snapshot error:", repr(e))

    # send radar
    telegram_send_long(bot_token, chat_id, radar_text)

    # append small “trade plan” for TOP 1
    try:
        top = sorted(results, key=lambda x: x["score"], reverse=True)[0]
        plan = trade_plan(cfg, top)
        telegram_send_long(bot_token, chat_id, f"🧾 TRADE PLAN ({top['ticker']})\n{plan}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
