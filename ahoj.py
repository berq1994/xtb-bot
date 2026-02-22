import os
import json
import math
import time
import requests
import feedparser
import yfinance as yf

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# YAML config (optional)
try:
    import yaml
except Exception:
    yaml = None

# ============================================================
# TIMEZONE
# ============================================================
TZ_NAME = os.getenv("TIMEZONE", "Europe/Prague").strip()
TZ = ZoneInfo(TZ_NAME)

def now_local() -> datetime:
    return datetime.now(TZ)

def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")

def today_str() -> str:
    return now_local().strftime("%Y-%m-%d")

def is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5

def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm

# ============================================================
# ENV (Secrets)
# ============================================================
TELEGRAM_TOKEN = (os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
CHAT_ID = str(os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or "").strip()
FMP_API_KEY = (os.getenv("FMPAPIKEY") or os.getenv("FMP_API_KEY") or "").strip()

RUN_MODE = (os.getenv("RUN_MODE") or "run").strip().lower()  # run | backfill | learn

# Report times (local)
PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()

# Alerts window + threshold
ALERT_START = os.getenv("ALERT_START", "12:00").strip()
ALERT_END = os.getenv("ALERT_END", "21:00").strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3").strip())  # % from today's OPEN

NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2").strip())
TOP_N = int(os.getenv("TOP_N", "5").strip())

# backfill range
BACKFILL_START = os.getenv("BACKFILL_START", "2025-01-01").strip()
BACKFILL_END = os.getenv("BACKFILL_END", "").strip()  # empty => today

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ============================================================
# STATE DIR
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_ALERTS_FILE = os.path.join(STATE_DIR, "last_alerts.json")

PROFILES_FILE = os.path.join(STATE_DIR, "profiles.json")
LEARNED_WEIGHTS_FILE = os.path.join(STATE_DIR, "learned_weights.json")
SNAPSHOTS_FILE = os.path.join(STATE_DIR, "snapshots.jsonl")
HISTORY_DIR = os.path.join(STATE_DIR, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

# ============================================================
# CONFIG (optional config.yml)
# ============================================================
DEFAULT_CONFIG_PATHS = ["config.yml", "config.yaml", ".github/config.yml", ".github/config.yaml"]

def load_cfg():
    if yaml is None:
        return {}
    path = None
    for p in DEFAULT_CONFIG_PATHS:
        if os.path.exists(p):
            path = p
            break
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

CFG = load_cfg()

def cfg_get(path, default=None):
    try:
        cur = CFG
        for part in path.split("."):
            if not isinstance(cur, dict):
                return default
            cur = cur.get(part)
        return default if cur is None else cur
    except Exception:
        return default

def read_text(path: str, default="") -> str:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return default

def write_text(path: str, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

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

# ============================================================
# TELEGRAM
# ============================================================
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

def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram není nastaven: chybí token/chat_id.")
        return
    try:
        r = requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=35
        )
        print("Telegram status:", r.status_code)
        if r.status_code != 200:
            print("Telegram odpověď:", r.text[:500])
    except Exception as e:
        print("Telegram error:", e)

def telegram_send_long(text: str):
    for part in chunk_text(text):
        telegram_send(part)

# ============================================================
# FMP API (optional)
# ============================================================
def fmp_get(path: str, params=None):
    key = (FMP_API_KEY or cfg_get("fmp_api_key", "") or "").strip()
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

# ============================================================
# TICKERS (ALL)
# ============================================================
def portfolio_from_cfg():
    items = cfg_get("portfolio", [])
    out = []
    if isinstance(items, list):
        for row in items:
            if isinstance(row, dict) and row.get("ticker"):
                out.append(str(row.get("ticker")).strip().upper())
    return out

PORTFOLIO = portfolio_from_cfg() or [
    "NVDA","TSM","MSFT","CVX","CSG","SGLD","NVO","NBIS","IREN","LEU"
]

WATCHLIST_CFG = cfg_get("watchlist", [])
WATCHLIST = []
if isinstance(WATCHLIST_CFG, list) and WATCHLIST_CFG:
    WATCHLIST = [str(x).strip().upper() for x in WATCHLIST_CFG if str(x).strip()]
else:
    WATCHLIST = ["SPY","QQQ","SMH"]

# IMPORTANT: new_candidates can be bool by mistake -> sanitize
def new_candidates_from_cfg():
    raw = cfg_get("new_candidates", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raw = []
    out = [str(x).strip().upper() for x in raw]
    return [x for x in out if x]

NEW_CANDIDATES = new_candidates_from_cfg() or ["ASML","AMD","AVGO","CRWD","LLT"]

# You said: BACKFILL FOR ALL -> portfolio + watchlist + new candidates + extra universe
EXTRA_UNIVERSE = cfg_get("extra_universe", [])
if isinstance(EXTRA_UNIVERSE, list):
    EXTRA_UNIVERSE = [str(x).strip().upper() for x in EXTRA_UNIVERSE if str(x).strip()]
else:
    EXTRA_UNIVERSE = [
        # AI/semis/metals starter set (safe)
        "PLTR","AMZN","AAPL","GOOGL","META","TSLA","MSFT",
        "SMCI","ARM","MU","QCOM","ASML","AVGO","AMD","AMAT","LRCX","KLAC",
        "FCX","SCCO","RIO","BHP","AA","TECK","VALE","ALB",
        "GLD","SLV"
    ]

ALL_TICKERS = sorted(set(PORTFOLIO + WATCHLIST + NEW_CANDIDATES + EXTRA_UNIVERSE))

# ============================================================
# DATA HELPERS
# ============================================================
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

def bar(pct: float, width: int = 14) -> str:
    if pct is None:
        return ""
    a = min(abs(pct), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)

def y_history_daily(ticker: str, start: str, end: str):
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end,
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False
        )
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None

def daily_last_prev(ticker: str):
    # Prefer FMP when available
    data = fmp_get("v3/historical-price-full/" + ticker, {"serietype": "line", "timeseries": 5})
    if isinstance(data, dict):
        hist = data.get("historical")
        if isinstance(hist, list) and len(hist) >= 2:
            c0 = safe_float(hist[0].get("close"))
            c1 = safe_float(hist[1].get("close"))
            if c0 is not None and c1 is not None:
                return c0, c1, "FMP"

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

def ret_5d_yahoo(ticker: str):
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

def rel_strength_5d(ticker: str, bench="SPY"):
    r_t = ret_5d_yahoo(ticker)
    r_b = ret_5d_yahoo(bench)
    if r_t is None or r_b is None:
        return None
    return r_t - r_b

# ============================================================
# NEWS (RSS + FMP)
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

def news_fmp(ticker: str, limit: int):
    data = fmp_get("v3/stock_news", {"tickers": ticker, "limit": limit})
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

def combined_news(ticker: str, limit_each: int):
    items = []
    items += news_fmp(ticker, limit_each)
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
# EARNINGS (FMP calendar)
# ============================================================
def fmp_next_earnings_date(ticker: str):
    data = fmp_get("v3/earning_calendar", {"symbol": ticker})
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

def days_to_earnings(ticker: str):
    ed = fmp_next_earnings_date(ticker)
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
# MARKET REGIME (SPY trend + VIX)
# ============================================================
def market_regime():
    label = "NEUTRÁLNÍ"
    detail = []
    try:
        spy = yf.Ticker("SPY").history(period="3mo", interval="1d")
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

# ============================================================
# WEIGHTS (learned weekly) + scoring
# ============================================================
DEFAULT_WEIGHTS = {
    "momentum": float(cfg_get("weights.momentum", 0.25)),
    "rel_strength": float(cfg_get("weights.rel_strength", 0.20)),
    "volatility_volume": float(cfg_get("weights.volatility_volume", 0.15)),
    "catalyst": float(cfg_get("weights.catalyst", 0.20)),
    "market_regime": float(cfg_get("weights.market_regime", 0.20)),
}

def load_weights():
    w = dict(DEFAULT_WEIGHTS)
    learned = read_json(LEARNED_WEIGHTS_FILE, {})
    if isinstance(learned, dict):
        for k in w:
            if k in learned and isinstance(learned[k], (int, float)):
                w[k] = float(learned[k])
    # normalize
    s = sum(w.values())
    if s > 0:
        for k in w:
            w[k] = w[k] / s
    return w

def clamp(x, lo=0.0, hi=10.0):
    return max(lo, min(hi, x))

def momentum_score_1d(pct1d):
    if pct1d is None:
        return 0.0
    a = abs(pct1d)
    return clamp((a / 8.0) * 10.0, 0.0, 10.0)

def rs_score(rs):
    if rs is None:
        return 0.0
    return clamp((rs + 5.0) * 1.0, 0.0, 10.0)

def vol_score(vol_ratio):
    if vol_ratio is None:
        return 0.0
    return clamp((vol_ratio - 1.0) * 6.0, 0.0, 10.0)

def catalyst_score(news_items, days_earn):
    s = 0.0
    if news_items and len(news_items) > 0:
        s += min(4.0, 1.0 + 0.7 * len(news_items))
    if days_earn is not None:
        if days_earn <= 2:
            s += 6.0
        elif days_earn <= 7:
            s += 4.0
        elif days_earn <= 14:
            s += 2.0
    return clamp(s, 0.0, 10.0)

def regime_score(regime_label):
    if regime_label == "RISK-ON":
        return 10.0
    if regime_label == "RISK-OFF":
        return 0.0
    return 5.0

def total_score(weights, mom, rs, vol, cat, reg):
    return (
        weights["momentum"] * mom +
        weights["rel_strength"] * rs +
        weights["volatility_volume"] * vol +
        weights["catalyst"] * cat +
        weights["market_regime"] * reg
    )

def action_suggestion(score, regime_label, days_earn):
    # “aktuální co koupit/prodat” – soft, ale konkrétní:
    if days_earn is not None and days_earn <= 2:
        return "POZOR: earnings do 48h (vyšší riziko gapu)."
    if regime_label == "RISK-OFF":
        if score >= 7.8:
            return "SILNÉ, ale trh je RISK-OFF: spíš čekat na lepší timing / menší pozice."
        if score <= 3.2:
            return "SLABÉ + RISK-OFF: zvážit redukci / nedokupovat."
        return "RISK-OFF: držet konzervativně, nehonit vstupy."
    # risk-on / neutral
    if score >= 7.8:
        return "KANDIDÁT NA PŘIKOUPENÍ / VSTUP (dle tvého rizika)."
    if score <= 3.2:
        return "KANDIDÁT NA REDUKCI / PRODEJ (pokud to sedí do tvého plánu)."
    return "NEUTRÁL: spíš HOLD / čekat na katalyzátor."

def format_line(ticker, pct1d, score, suggestion, why, earn_note, rs, vol_ratio, src):
    pct_txt = "—" if pct1d is None else f"{pct1d:+.2f}% {bar(pct1d)}"
    rs_txt = "—" if rs is None else f"{rs:+.2f}%"
    vr_txt = "—" if vol_ratio is None else f"{vol_ratio:.2f}×"
    out = (
        f"{ticker}: {pct_txt} | score {score:.2f}\n"
        f"  RS(5D): {rs_txt} | Objem: {vr_txt} | Zdroj ceny: {src}\n"
    )
    if earn_note:
        out += f"  {earn_note}\n"
    out += f"  Proč: {why}\n"
    out += f"  Doporučení: {suggestion}\n"
    return out

# ============================================================
# SNAPSHOT LOGGING (for learning)
# ============================================================
def append_snapshot(row: dict):
    try:
        with open(SNAPSHOTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass

# ============================================================
# BUILD RADAR FOR LIST
# ============================================================
def build_radar(tickers, limit_news_each=NEWS_PER_TICKER):
    weights = load_weights()
    regime_label, regime_detail = market_regime()
    reg_s = regime_score(regime_label)

    rows = []
    for t in tickers:
        last, prev, src = daily_last_prev(t)
        pct1d = pct_change(last, prev)

        vr = volume_spike_yahoo(t)
        rs = rel_strength_5d(t, bench="SPY")

        news_items = combined_news(t, limit_news_each)[:limit_news_each]
        why = why_from_headlines(news_items)

        d_earn = days_to_earnings(t)
        enote = earnings_note(d_earn)

        mom = momentum_score_1d(pct1d)
        rss = rs_score(rs)
        vol = vol_score(vr)
        cat = catalyst_score(news_items, d_earn)

        score = total_score(weights, mom, rss, vol, cat, reg_s)
        suggestion = action_suggestion(score, regime_label, d_earn)

        # save snapshot for learning
        append_snapshot({
            "ts": now_local().isoformat(),
            "ticker": t,
            "last": last,
            "prev": prev,
            "pct1d": pct1d,
            "vol_ratio": vr,
            "rs5d": rs,
            "news_count": len(news_items),
            "days_to_earnings": d_earn,
            "market_regime": regime_label,
            "score": score,
            "factors": {
                "momentum": mom,
                "rel_strength": rss,
                "volatility_volume": vol,
                "catalyst": cat,
                "market_regime": reg_s
            }
        })

        rows.append({
            "ticker": t,
            "pct1d": pct1d,
            "score": score,
            "suggestion": suggestion,
            "why": why,
            "earn_note": enote,
            "rs": rs,
            "vol_ratio": vr,
            "src": src
        })

    rows.sort(key=lambda x: x["score"], reverse=True)
    header = (
        f"📡 INVESTIČNÍ RADAR ({today_str()} {hm(now_local())})\n"
        f"Režim trhu: {regime_label} ({regime_detail})\n"
        f"Váhy (learned): {json.dumps(load_weights(), ensure_ascii=False)}\n"
        "—\n"
    )
    return header, rows

# ============================================================
# REPORTS (12:00 / 20:00)
# ============================================================
def should_run_once_per_day(marker_file: str, target_hm: str, tolerance_min: int = 12):
    now = now_local()
    last = read_text(marker_file, "")
    if last == today_str():
        return False
    try:
        th, tm = target_hm.split(":")
        target = now.replace(hour=int(th), minute=int(tm), second=0, microsecond=0)
    except Exception:
        target = now.replace(hour=12, minute=0, second=0, microsecond=0)
    delta = abs((now - target).total_seconds()) / 60.0
    return delta <= tolerance_min

def mark_ran(marker_file: str):
    write_text(marker_file, today_str())

def report_12():
    header, rows = build_radar(ALL_TICKERS, limit_news_each=NEWS_PER_TICKER)
    top = rows[:TOP_N]
    worst = sorted(rows, key=lambda x: x["score"])[:TOP_N]
    new = [r for r in rows if r["ticker"] in NEW_CANDIDATES][:TOP_N]

    msg = header
    msg += f"✅ TOP {TOP_N} (kandidáti):\n\n"
    for r in top:
        msg += format_line(**r) + "\n"

    msg += f"\n❌ WORST {TOP_N} (pozor):\n\n"
    for r in worst:
        msg += format_line(**r) + "\n"

    # Earnings blízko (portfolio)
    msg += "\n📅 Earnings – PORTFOLIO (riziko do 14 dní):\n"
    for t in PORTFOLIO:
        d = days_to_earnings(t)
        if d is not None and d <= 14:
            msg += f"- {t}: za {d} dní. {earnings_note(d)}\n"
    msg += "\nPozn.: Doporučení jsou podpůrná (nejsou garance)."

    telegram_send_long(msg)

def report_20():
    header, rows = build_radar(ALL_TICKERS, limit_news_each=1)
    top = rows[:TOP_N]
    worst = sorted(rows, key=lambda x: x["score"])[:TOP_N]
    new = [r for r in rows if r["ticker"] in NEW_CANDIDATES][:TOP_N]

    msg = header
    msg += f"🌙 VEČERNÍ SHRUTÍ – TOP {TOP_N}:\n\n"
    for r in top:
        msg += format_line(**r) + "\n"

    msg += f"\n⚠️ VEČERNÍ – WORST {TOP_N}:\n\n"
    for r in worst:
        msg += format_line(**r) + "\n"

    msg += f"\n🆕 NOVÉ NADĚJNÉ (z listu):\n"
    for r in new:
        msg += f"- {r['ticker']}: score {r['score']:.2f} | {r['suggestion']}\n"
    msg += "\nPozn.: Doporučení jsou podpůrná (nejsou garance)."

    telegram_send_long(msg)

# ============================================================
# ALERTS (intraday)
# ============================================================
def load_last_alerts():
    return read_json(LAST_ALERTS_FILE, {})

def save_last_alerts(data):
    write_json(LAST_ALERTS_FILE, data)

def check_intraday_alerts():
    now = now_local()
    if not is_weekday(now):
        return
    nowhm = hm(now)
    if not in_window(nowhm, ALERT_START, ALERT_END):
        return

    last_alerts = load_last_alerts()
    todays = last_alerts.get(today_str(), {})

    hits = []
    for t in ALL_TICKERS:
        got = intraday_open_last_yahoo(t)
        if not got:
            continue
        o, last = got
        pct = pct_change(last, o)
        if pct is None:
            continue
        if abs(pct) >= ALERT_THRESHOLD:
            if todays.get(t):
                continue
            todays[t] = True
            why = why_from_headlines(combined_news(t, 2)[:2])
            hits.append((t, pct, why))

    if hits:
        hits.sort(key=lambda x: abs(x[1]), reverse=True)
        msg = f"🚨 ALERT ({today_str()} {nowhm}) – pohyb od OPEN ≥ {ALERT_THRESHOLD:.1f}%\n"
        for t, pct, why in hits[:12]:
            msg += f"\n{t}: {pct:+.2f}% {bar(pct)}\nProč: {why}\n"
        telegram_send_long(msg.strip())

    last_alerts[today_str()] = todays
    save_last_alerts(last_alerts)

# ============================================================
# BACKFILL (history store)
# ============================================================
def backfill_all():
    end = BACKFILL_END.strip() or date.today().strftime("%Y-%m-%d")
    start = BACKFILL_START.strip()

    telegram_send(f"🧱 BACKFILL start: {start} → {end} | tickery: {len(ALL_TICKERS)}")

    ok = 0
    fail = 0
    for t in ALL_TICKERS:
        df = y_history_daily(t, start, end)
        if df is None:
            fail += 1
            continue
        path = os.path.join(HISTORY_DIR, f"{t}.csv")
        df.to_csv(path)
        ok += 1

    telegram_send(f"✅ BACKFILL hotovo. OK={ok}, FAIL={fail}. Data uložena v {HISTORY_DIR}/")

# ============================================================
# WEEKLY LEARN (simple calibration)
# ============================================================
def parse_snapshots(last_days: int = 60):
    cutoff = now_local() - timedelta(days=last_days)
    rows = []
    if not os.path.exists(SNAPSHOTS_FILE):
        return rows
    with open(SNAPSHOTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                ts = datetime.fromisoformat(r.get("ts"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=TZ)
                if ts >= cutoff:
                    rows.append(r)
            except Exception:
                continue
    return rows

def future_return_from_history(ticker: str, asof_date: str, horizon_days: int):
    # use stored history csv if available
    path = os.path.join(HISTORY_DIR, f"{ticker}.csv")
    if not os.path.exists(path):
        return None
    try:
        # lightweight CSV read
        import csv
        with open(path, newline="", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        # find row by date index column name possibly "Date" or first col blank
        # yfinance CSV created with index, usually first column is "Date"
        # We'll handle both.
        dates = []
        closes = []
        for row in reader:
            d = row.get("Date") or row.get("")
            if not d:
                # some formats use first key
                d = list(row.keys())[0]
            # best effort: Date is in first column in yfinance csv, DictReader will name it 'Date'
            # If not, skip
            if not row.get("Close"):
                continue
            dates.append(d)
            closes.append(safe_float(row.get("Close")))
        if not dates or not closes:
            return None

        # map date->close
        m = {}
        for d, c in zip(dates, closes):
            if c is not None:
                m[d] = c

        if asof_date not in m:
            return None

        # find next available date horizon_days ahead (trading days not calendar)
        # We'll walk forward by sorted dates
        sdates = sorted(m.keys())
        idx = sdates.index(asof_date)
        idx2 = idx + horizon_days
        if idx2 >= len(sdates):
            return None
        c0 = m[sdates[idx]]
        c1 = m[sdates[idx2]]
        return pct_change(c1, c0)
    except Exception:
        return None

def calibrate_weights():
    # Simple robust calibration: maximize correlation between factors and future returns
    # using horizons 1/3/5 trading days (average).
    snaps = parse_snapshots(last_days=90)
    if len(snaps) < 200:
        telegram_send("ℹ️ WEEKLY LEARN: málo dat pro kalibraci (zatím).")
        return

    # collect samples
    samples = []
    for r in snaps:
        t = r.get("ticker")
        ts = r.get("ts")
        if not t or not ts:
            continue
        d = ts[:10]  # YYYY-MM-DD
        f = r.get("factors") or {}
        if not isinstance(f, dict):
            continue

        ret1 = future_return_from_history(t, d, 1)
        ret3 = future_return_from_history(t, d, 3)
        ret5 = future_return_from_history(t, d, 5)
        rets = [x for x in [ret1, ret3, ret5] if isinstance(x, (int, float))]
        if not rets:
            continue
        y = sum(rets) / len(rets)

        samples.append((f, y))

    if len(samples) < 200:
        telegram_send("ℹ️ WEEKLY LEARN: po napárování historie je pořád málo vzorků.")
        return

    # compute simple Pearson corr per factor (absolute), turn into weights
    keys = ["momentum", "rel_strength", "volatility_volume", "catalyst", "market_regime"]
    # extract arrays
    import statistics
    def pearson(xs, ys):
        try:
            mx = statistics.mean(xs)
            my = statistics.mean(ys)
            num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
            deny = math.sqrt(sum((y - my) ** 2 for y in ys))
            if denx == 0 or deny == 0:
                return 0.0
            return num / (denx * deny)
        except Exception:
            return 0.0

    y_arr = [y for (_, y) in samples]
    corrs = {}
    for k in keys:
        x_arr = []
        for (f, _) in samples:
            x_arr.append(safe_float(f.get(k)) or 0.0)
        c = pearson(x_arr, y_arr)
        corrs[k] = abs(c)

    # convert to weights with floor to avoid zeroing out
    floor = 0.05
    raw = {k: max(floor, corrs.get(k, 0.0)) for k in keys}
    s = sum(raw.values())
    learned = {k: raw[k] / s for k in keys}

    write_json(LEARNED_WEIGHTS_FILE, learned)
    telegram_send("🧠 WEEKLY LEARN: hotovo. Nové learned váhy uloženy:\n" + json.dumps(learned, ensure_ascii=False, indent=2))

# ============================================================
# MAIN
# ============================================================
def main():
    print(f"✅ Running mode: {RUN_MODE} | TZ={TZ_NAME} | now={now_local().isoformat()} | tickers={len(ALL_TICKERS)}")

    if RUN_MODE == "backfill":
        backfill_all()
        return

    if RUN_MODE == "learn":
        calibrate_weights()
        return

    # Normal run
    check_intraday_alerts()

    # 12:00 report once per day (tolerance)
    if should_run_once_per_day(LAST_PREMARKET_DATE_FILE, PREMARKET_TIME, tolerance_min=12):
        report_12()
        mark_ran(LAST_PREMARKET_DATE_FILE)

    # 20:00 report once per day (tolerance)
    if should_run_once_per_day(LAST_EVENING_DATE_FILE, EVENING_TIME, tolerance_min=12):
        report_20()
        mark_ran(LAST_EVENING_DATE_FILE)

def should_run_once_per_day(marker_file: str, target_hm: str, tolerance_min: int = 12):
    now = now_local()
    last = read_text(marker_file, "")
    if last == today_str():
        return False
    try:
        th, tm = target_hm.split(":")
        target = now.replace(hour=int(th), minute=int(tm), second=0, microsecond=0)
    except Exception:
        target = now.replace(hour=12, minute=0, second=0, microsecond=0)
    delta = abs((now - target).total_seconds()) / 60.0
    return delta <= tolerance_min

def mark_ran(marker_file: str):
    write_text(marker_file, today_str())

if __name__ == "__main__":
    main()
