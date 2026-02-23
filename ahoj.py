import os
import re
import json
import math
import csv
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

# Matplotlib for email charts (optional; if missing, email will be without charts)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    plt = None

# Email (Gmail SMTP) – optional
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


# ============================================================
# BEZPEČNOST / DISCLAIMER (nízká váha, ale fér)
# ============================================================
DISCLAIMER = (
    "⚠️ Upozornění: Toto je automatizovaný informační radar, nikoli investiční poradenství. "
    "Signály a skóre jsou heuristiky. Rozhodnutí vždy ověř a řiď se vlastním plánem a rizikem."
)


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
# ENV (Secrets) – fallback na vaše historické názvy
# ============================================================
def env_first(*names, default=""):
    for n in names:
        v = os.getenv(n)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return default

# Telegram – podporujeme oboje: (TELEGRAMTOKEN/CHATID) i (TG_BOT_TOKEN/TG_CHAT_ID)
TELEGRAM_TOKEN = env_first("TELEGRAMTOKEN", "TG_BOT_TOKEN")
CHAT_ID = env_first("CHATID", "TG_CHAT_ID")

# FMP – oboje: (FMPAPIKEY) i (FMP_API_KEY)
FMP_API_KEY = env_first("FMPAPIKEY", "FMP_API_KEY")

# RUN MODE: run | backfill | learn
RUN_MODE = env_first("RUN_MODE", default="run").lower()

# Časy reportů (lokální čas Praha)
PREMARKET_TIME = env_first("PREMARKET_TIME", default="12:00")
EVENING_TIME = env_first("EVENING_TIME", default="20:00")

# Alert okno a práh – změna od dnešního OPEN (US open; skript bere "open dne" z intraday)
ALERT_START = env_first("ALERT_START", default="12:00")
ALERT_END = env_first("ALERT_END", default="21:00")
ALERT_THRESHOLD = float(env_first("ALERT_THRESHOLD", default="3"))

# Kolik zpráv na ticker (news)
NEWS_PER_TICKER = int(env_first("NEWS_PER_TICKER", default="2"))

# Top/bottom/new počty v evening summary
TOP_N = int(env_first("TOP_N", default="5"))

# Investiční příležitosti – omezit na pracovní dny
OPPORTUNITY_WEEKDAYS_ONLY = (env_first("OPPORTUNITY_WEEKDAYS_ONLY", default="true").lower() == "true")

# Backfill rozsah
BACKFILL_START = env_first("BACKFILL_START", default="2025-01-01")
BACKFILL_END = env_first("BACKFILL_END", default="")  # prázdné => dnes

# Email – 1× denně
EMAIL_ENABLED = (env_first("EMAIL_ENABLED", default="false").lower() == "true")
EMAIL_SENDER = env_first("EMAIL_SENDER", default="")
EMAIL_RECEIVER = env_first("EMAIL_RECEIVER", default="")
GMAILPASSWORD = env_first("GMAILPASSWORD", default="")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ============================================================
# STATE DIR
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_EMAIL_DATE_FILE = os.path.join(STATE_DIR, "last_email_date.txt")

# alerty: aby se neposílalo dokola, držíme cache odeslaných alertů per den
LAST_ALERTS_FILE = os.path.join(STATE_DIR, "last_alerts.json")

# cache profilu firem
PROFILES_FILE = os.path.join(STATE_DIR, "profiles.json")

# learned weights
LEARNED_WEIGHTS_FILE = os.path.join(STATE_DIR, "learned_weights.json")

# snapshots (denní log scoringu)
SNAPSHOTS_FILE = os.path.join(STATE_DIR, "snapshots.jsonl")

# history pro backfill
HISTORY_DIR = os.path.join(STATE_DIR, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)


# ============================================================
# CONFIG (optional config.yml) + jednoduché ${ENV} substituce
# ============================================================
DEFAULT_CONFIG_PATHS = ["config.yml", "config.yaml", ".github/config.yml", ".github/config.yaml"]

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

def _expand_env(obj):
    """Rekurzivně nahradí ${VAR} hodnotami z environmentu, pokud existují."""
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env(v) for v in obj]
    if isinstance(obj, str):
        def repl(m):
            var = m.group(1)
            return os.getenv(var, m.group(0))
        return _ENV_PATTERN.sub(repl, obj)
    return obj

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
            raw = yaml.safe_load(f) or {}
            return _expand_env(raw)
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
# PŘEKLADY (do češtiny) – volitelné
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
    if not text:
        return ""
    key = text.strip()
    if len(key) < 5:
        return key
    if key in _TRANSLATE_CACHE:
        return _TRANSLATE_CACHE[key]
    if _TRANSLATOR is None:
        _TRANSLATE_CACHE[key] = key
        return key
    try:
        out = _TRANATOR_SAFE(key)
        _TRANSLATE_CACHE[key] = out
        return out
    except Exception:
        _TRANSLATE_CACHE[key] = key
        return key

def _TRANATOR_SAFE(s: str) -> str:
    # extra guard against occasional translator errors
    try:
        return _TRANSLATOR.translate(s)
    except Exception:
        return s


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
            print("Telegram odpověď:", r.text[:800])
    except Exception as e:
        print("Telegram error:", e)

def telegram_send_long(text: str):
    for part in chunk_text(text):
        telegram_send(part)


# ============================================================
# EMAIL (Gmail SMTP) – 1× denně
# ============================================================
def email_send(subject: str, body_text: str, image_paths=None):
    if not EMAIL_ENABLED:
        return
    if not (EMAIL_SENDER and EMAIL_RECEIVER and GMAILPASSWORD):
        print("⚠️ Email zapnutý, ale chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject

    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    image_paths = image_paths or []
    for path in image_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
                msg.attach(img)
        except Exception as e:
            print("⚠️ Příloha obrázku chyba:", path, e)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=40)
        server.ehlo()
        server.starttls()
        server.login(EMAIL_SENDER, GMAILPASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print("✅ Email OK: odesláno")
    except Exception as e:
        print("❌ Email ERROR:", repr(e))


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
# TICKERS (from config)
# ============================================================
def portfolio_rows_from_cfg():
    items = cfg_get("portfolio", [])
    out = []
    if isinstance(items, list):
        for row in items:
            if isinstance(row, dict) and row.get("ticker"):
                out.append(row)
    return out

def tickers_from_rows(rows):
    out = []
    for r in rows:
        t = str(r.get("ticker", "")).strip().upper()
        if t:
            out.append(t)
    return out

PORTFOLIO_ROWS = portfolio_rows_from_cfg()
PORTFOLIO = tickers_from_rows(PORTFOLIO_ROWS) or [
    "NVDA","TSM","MSFT","CVX","CSG","SGLD","NVO","NBIS","IREN","LEU"
]

WATCHLIST_CFG = cfg_get("watchlist", [])
WATCHLIST = []
if isinstance(WATCHLIST_CFG, list) and WATCHLIST_CFG:
    WATCHLIST = [str(x).strip().upper() for x in WATCHLIST_CFG if str(x).strip()]
else:
    WATCHLIST = ["SPY","QQQ","SMH"]

def new_candidates_from_cfg():
    raw = cfg_get("new_candidates", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raw = []
    out = [str(x).strip().upper() for x in raw]
    return [x for x in out if x]

NEW_CANDIDATES = new_candidates_from_cfg() or ["ASML","AMD","AVGO","CRWD","LLT"]

EXTRA_UNIVERSE = cfg_get("extra_universe", [])
if isinstance(EXTRA_UNIVERSE, list):
    EXTRA_UNIVERSE = [str(x).strip().upper() for x in EXTRA_UNIVERSE if str(x).strip()]
else:
    EXTRA_UNIVERSE = [
        # AI/semis/metals starter set
        "PLTR","AMZN","AAPL","GOOGL","META","TSLA","MSFT",
        "SMCI","ARM","MU","QCOM","ASML","AVGO","AMD","AMAT","LRCX","KLAC",
        "FCX","SCCO","RIO","BHP","AA","TECK","VALE","ALB",
        "GLD","SLV"
    ]

ALL_TICKERS = sorted(set(PORTFOLIO + WATCHLIST + NEW_CANDIDATES + EXTRA_UNIVERSE))

# symbol mapping (když Yahoo nezná – můžeš doplnit v config.yml)
SYMBOL_MAP = cfg_get("symbol_map", {})
if not isinstance(SYMBOL_MAP, dict):
    SYMBOL_MAP = {}

def resolve_symbol(ticker: str):
    v = SYMBOL_MAP.get(ticker)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return ticker


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

def daily_last_prev(ticker: str):
    t = resolve_symbol(ticker)

    # Prefer FMP when available
    data = fmp_get("v3/historical-price-full/" + t, {"serietype": "line", "timeseries": 5})
    if isinstance(data, dict):
        hist = data.get("historical")
        if isinstance(hist, list) and len(hist) >= 2:
            c0 = safe_float(hist[0].get("close"))
            c1 = safe_float(hist[1].get("close"))
            if c0 is not None and c1 is not None:
                return c0, c1, "FMP"

    # Yahoo fallback
    try:
        h = yf.Ticker(t).history(period="10d", interval="1d")
        if h is None or h.empty:
            return None, None, "—"
        closes = h["Close"].dropna()
        if len(closes) < 2:
            return None, None, "—"
        return float(closes.iloc[-1]), float(closes.iloc[-2]), "Yahoo"
    except Exception:
        return None, None, "—"

def intraday_open_last_yahoo(ticker: str):
    t = resolve_symbol(ticker)
    try:
        h = yf.Ticker(t).history(period="1d", interval="5m")
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
    t = resolve_symbol(ticker)
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

def ret_5d_yahoo(ticker: str):
    t = resolve_symbol(ticker)
    try:
        h = yf.Ticker(t).history(period="8d", interval="1d")
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
    t = resolve_symbol(ticker)
    data = fmp_get("v3/stock_news", {"tickers": t, "limit": limit})
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
    t = resolve_symbol(ticker)
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"
    return [("Yahoo", title, link) for title, link in rss_entries(url, limit)]

def news_seekingalpha_rss(ticker: str, limit: int):
    # Seeking Alpha RSS per symbol
    url = f"https://seekingalpha.com/symbol/{ticker}.xml"
    return [("SeekingAlpha", title, link) for title, link in rss_entries(url, limit)]

def news_google_rss(ticker: str, limit: int):
    q = requests.utils.quote(f"{ticker} stock OR {ticker} earnings OR {ticker} guidance")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return [("GoogleNews", title, link) for title, link in rss_entries(url, limit)]

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
    t = resolve_symbol(ticker)
    data = fmp_get("v3/earning_calendar", {"symbol": t})
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
# PROFIL FIRMY (FMP -> Yahoo fallback) + cache
# ============================================================
def profiles_load():
    data = read_json(PROFILES_FILE, {})
    return data if isinstance(data, dict) else {}

def profiles_save(d):
    write_json(PROFILES_FILE, d)

def get_profile(ticker: str):
    cache = profiles_load()
    if ticker in cache:
        return cache[ticker]

    prof = {"name": ticker, "sector": "", "industry": "", "description": ""}

    # FMP profile
    data = fmp_get("v3/profile", {"symbol": resolve_symbol(ticker)})
    if isinstance(data, list) and data:
        row = data[0]
        prof["name"] = (row.get("companyName") or ticker).strip()
        prof["sector"] = (row.get("sector") or "").strip()
        prof["industry"] = (row.get("industry") or "").strip()
        prof["description"] = (row.get("description") or "").strip()

    # Yahoo fallback
    if prof["name"] == ticker:
        try:
            info = yf.Ticker(resolve_symbol(ticker)).info or {}
            prof["name"] = (info.get("longName") or info.get("shortName") or ticker).strip()
            prof["sector"] = prof["sector"] or (info.get("sector") or "").strip()
            prof["industry"] = prof["industry"] or (info.get("industry") or "").strip()
            prof["description"] = prof["description"] or (info.get("longBusinessSummary") or "").strip()
        except Exception:
            pass

    cache[ticker] = prof
    profiles_save(cache)
    return prof


# ============================================================
# WEIGHTS (learned weekly) + scoring (SOFT/HARD)
# ============================================================
DEFAULT_WEIGHTS = {
    "momentum": float(cfg_get("weights.momentum", 0.25)),
    "rel_strength": float(cfg_get("weights.rel_strength", 0.20)),
    "volatility_volume": float(cfg_get("weights.volatility_volume", 0.15)),
    "catalyst": float(cfg_get("weights.catalyst", 0.20)),
    "market_regime": float(cfg_get("weights.market_regime", 0.20)),
}

ADVICE_MODE = str(cfg_get("advice_mode", "SOFT")).strip().upper()
BENCH = str(cfg_get("benchmarks.spy", "SPY")).strip().upper()

def load_weights():
    w = dict(DEFAULT_WEIGHTS)
    learned = read_json(LEARNED_WEIGHTS_FILE, {})
    if isinstance(learned, dict):
        for k in w:
            if k in learned and isinstance(learned[k], (int, float)):
                w[k] = float(learned[k])

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

def soft_suggestion(score, regime_label, days_earn):
    if days_earn is not None and days_earn <= 2:
        return "POZOR: earnings do 48h (vyšší riziko gapu)."
    if regime_label == "RISK-OFF":
        if score >= 7.8:
            return "Silné, ale trh RISK-OFF: spíš čekat na timing / menší pozice."
        if score <= 3.2:
            return "Slabé + RISK-OFF: zvážit redukci / nedokupovat."
        return "RISK-OFF: držet konzervativně, nehonit vstupy."
    if score >= 7.8:
        return "Silný kandidát (zvaž vstup/přikoupení dle plánu)."
    if score <= 3.2:
        return "Slabý kandidát (zvaž redukci, pokud to sedí do plánu)."
    return "Neutrál: spíš HOLD / čekat na katalyzátor."

def hard_suggestion(score, regime_label, days_earn):
    if days_earn is not None and days_earn <= 2:
        return "HOLD (earnings do 48h – vyčkej)."
    if regime_label == "RISK-OFF":
        if score >= 8.2:
            return "BUY (opatrně, RISK-OFF)"
        if score <= 2.8:
            return "SELL/REDUCE"
        return "HOLD"
    if score >= 8.2:
        return "BUY"
    if score <= 2.8:
        return "SELL/REDUCE"
    return "HOLD"

def suggestion(score, regime_label, days_earn):
    if ADVICE_MODE == "HARD":
        return hard_suggestion(score, regime_label, days_earn)
    return soft_suggestion(score, regime_label, days_earn)


# ============================================================
# SNAPSHOTS (log pro learning a audit)
# ============================================================
def append_snapshot(payload: dict):
    try:
        with open(SNAPSHOTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ============================================================
# ALERTS STATE
# ============================================================
def alerts_load():
    d = read_json(LAST_ALERTS_FILE, {})
    return d if isinstance(d, dict) else {}

def alerts_save(d):
    write_json(LAST_ALERTS_FILE, d)


# ============================================================
# CHARTS for Email (top movers)
# ============================================================
def make_price_chart(ticker: str, days: int = 30):
    if plt is None:
        return None
    t = resolve_symbol(ticker)
    try:
        h = yf.Ticker(t).history(period=f"{days}d", interval="1d")
        if h is None or h.empty:
            return None
        closes = h["Close"].dropna()
        if closes.empty:
            return None

        plt.figure(figsize=(7, 3.2))
        plt.plot(closes.index, closes.values)
        plt.title(f"{ticker} – posledních {days} dní")
        plt.tight_layout()

        fn = os.path.join(STATE_DIR, f"chart_{ticker}.png")
        plt.savefig(fn, bbox_inches="tight")
        plt.close()
        return fn
    except Exception:
        return None


# ============================================================
# REPORT BUILDERS
# ============================================================
def collect_metrics(ticker: str, regime_label: str):
    last, prev, src = daily_last_prev(ticker)
    pct1d = pct_change(last, prev)

    rs = rel_strength_5d(ticker, bench=BENCH)
    volr = volume_spike_yahoo(ticker)
    news = combined_news(ticker, NEWS_PER_TICKER)
    earn_days = days_to_earnings(ticker)

    weights = load_weights()

    mom_s = momentum_score_1d(pct1d)
    rs_s = rs_score(rs)
    vol_s = vol_score(volr)
    cat_s = catalyst_score(news, earn_days)
    reg_s = regime_score(regime_label)

    score = total_score(weights, mom_s, rs_s, vol_s, cat_s, reg_s)
    why = why_from_headlines(news)
    sug = suggestion(score, regime_label, earn_days)

    prof = get_profile(ticker)

    return {
        "ticker": ticker,
        "name": prof.get("name", ticker),
        "sector": prof.get("sector", ""),
        "industry": prof.get("industry", ""),
        "desc": prof.get("description", ""),
        "last": last,
        "prev": prev,
        "pct1d": pct1d,
        "rs5d": rs,
        "volr": volr,
        "earn_days": earn_days,
        "earn_note": earnings_note(earn_days),
        "news": news,
        "why": why,
        "score": score,
        "suggestion": sug,
        "price_src": src,
    }

def fmt_price(p):
    return "—" if p is None else f"{p:.2f}"

def fmt_pct(p):
    return "—" if p is None else f"{p:+.2f}%"

def fmt_float(x, digits=2):
    if x is None:
        return "—"
    return f"{x:.{digits}f}"

def shorten(text: str, n: int = 260):
    t = (text or "").strip()
    if len(t) <= n:
        return t
    return t[:n].rstrip() + "…"

def format_news_block(news_items, max_items=NEWS_PER_TICKER):
    if not news_items:
        return "  (žádné novinky)\n"
    out = ""
    for src, title, link in news_items[:max_items]:
        out += f"  • [{src}] {cz(title)}\n"
        if link:
            out += f"    {link}\n"
    return out

def build_premarket_report():
    regime_label, regime_detail = market_regime()
    ts = now_local().strftime("%d.%m.%Y %H:%M")

    lines = []
    lines.append(f"🕛 PREMARKET / RANNÍ PŘEHLED ({ts})")
    lines.append(f"Režim trhu: {regime_label} | {regime_detail}")
    lines.append("")

    # Portfolio – rychlý přehled + earnings warning
    lines.append("📌 Tvoje portfolio – denní změna + earnings:")
    for t in PORTFOLIO:
        m = collect_metrics(t, regime_label)
        lines.append(f"- {t} ({m['name']}): {fmt_price(m['last'])} ({fmt_pct(m['pct1d'])}) | score {m['score']:.2f} | {m['earn_note']}")
    lines.append("")
    lines.append("🗞️ Klíčové novinky (TOP):")
    # rychle vybereme tickery s největší “news” aktivitou
    news_rank = []
    for t in PORTFOLIO:
        n = combined_news(t, 3)
        news_rank.append((len(n), t, n))
    news_rank.sort(reverse=True)
    for _, t, n in news_rank[:3]:
        lines.append(f"\n{t}:")
        lines.append(format_news_block(n, max_items=3).rstrip())

    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)

def build_evening_summary():
    regime_label, regime_detail = market_regime()
    ts = now_local().strftime("%d.%m.%Y %H:%M")

    lines = []
    lines.append(f"🌙 VEČERNÍ SHR NUTÍ ({ts})")
    lines.append(f"Režim trhu: {regime_label} | {regime_detail}")
    lines.append("")

    # scoring pro portfolio + watchlist
    base_set = sorted(set(PORTFOLIO + WATCHLIST))
    metrics = []
    for t in base_set:
        metrics.append(collect_metrics(t, regime_label))

    # best/worst podle score
    metrics_sorted = sorted(metrics, key=lambda x: x["score"], reverse=True)
    best = metrics_sorted[:TOP_N]
    worst = list(reversed(metrics_sorted[-TOP_N:]))

    lines.append(f"✅ TOP {TOP_N} (nejlepší podle score):")
    for m in best:
        lines.append(f"- {m['ticker']} ({m['name']}): score {m['score']:.2f} | {fmt_price(m['last'])} ({fmt_pct(m['pct1d'])}) | {m['suggestion']} {m['earn_note']}")
        lines.append(f"  Proč: {m['why']}")
    lines.append("")

    lines.append(f"⛔ TOP {TOP_N} (nejhorší podle score):")
    for m in worst:
        lines.append(f"- {m['ticker']} ({m['name']}): score {m['score']:.2f} | {fmt_price(m['last'])} ({fmt_pct(m['pct1d'])}) | {m['suggestion']} {m['earn_note']}")
        lines.append(f"  Proč: {m['why']}")
    lines.append("")

    # new promising – z NEW_CANDIDATES (mimo portfolio)
    new_list = []
    for t in NEW_CANDIDATES:
        if t in PORTFOLIO:
            continue
        new_list.append(collect_metrics(t, regime_label))
    new_sorted = sorted(new_list, key=lambda x: x["score"], reverse=True)[:TOP_N]

    # respekt pracovních dnů pro příležitosti
    if OPPORTUNITY_WEEKDAYS_ONLY and not is_weekday(now_local()):
        lines.append("🧠 Nové nadějné (pracovní dny only): dnes se neposílá.")
    else:
        lines.append(f"🧠 TOP {TOP_N} nové nadějné (kandidáti):")
        for m in new_sorted:
            lines.append(f"- {m['ticker']} ({m['name']}): score {m['score']:.2f} | {fmt_price(m['last'])} ({fmt_pct(m['pct1d'])}) | {m['suggestion']} {m['earn_note']}")
            # co firma dělá + proč může uspět (stručně)
            desc = shorten(m.get("desc", ""), 300)
            if desc:
                lines.append(f"  Co dělá: {cz(desc)}")
            lines.append(f"  Proč to může fungovat: {m['why']}")
            # 1-2 news
            n = m.get("news", [])
            if n:
                lines.append("  Novinky:")
                lines.append(format_news_block(n, max_items=2).rstrip())

    lines.append("")
    lines.append(DISCLAIMER)

    # snapshot pro learning
    try:
        snap = {
            "date": today_str(),
            "time": hm(now_local()),
            "type": "evening",
            "regime": regime_label,
            "weights": load_weights(),
            "items": [
                {
                    "t": m["ticker"],
                    "score": m["score"],
                    "pct1d": m["pct1d"],
                    "rs5d": m["rs5d"],
                    "volr": m["volr"],
                    "earn_days": m["earn_days"],
                } for m in metrics_sorted[: min(len(metrics_sorted), 30)]
            ]
        }
        append_snapshot(snap)
    except Exception:
        pass

    return "\n".join(lines), best, worst, new_sorted


# ============================================================
# ALERTS: ± threshold od dnešního OPEN (intraday)
# ============================================================
def alerts_check_and_send():
    now = now_local()
    if not in_window(hm(now), ALERT_START, ALERT_END):
        return

    # alerty posíláme jen v pracovních dnech (US market days roughly); držíme to jednoduše
    if not is_weekday(now):
        return

    cache = alerts_load()
    dkey = today_str()
    if dkey not in cache:
        cache[dkey] = {}

    for t in PORTFOLIO:
        o_last = intraday_open_last_yahoo(t)
        if not o_last:
            continue
        o, last = o_last
        ch = pct_change(last, o)
        if ch is None:
            continue

        if abs(ch) < ALERT_THRESHOLD:
            continue

        direction = "UP" if ch > 0 else "DOWN"
        # bucket aby to neposílalo každých 15 min (pošle jednou za den a směr)
        key = f"{t}:{direction}"
        if cache[dkey].get(key):
            continue

        # news context
        n = combined_news(t, 2)
        why = why_from_headlines(n)

        msg = []
        msg.append(f"🚨 ALERT {t}: {ch:+.2f}% od dnešního OPEN")
        msg.append(f"OPEN: {o:.2f} | NOW: {last:.2f}")
        msg.append(f"Proč (heuristika): {why}")
        if n:
            msg.append("Novinky:")
            for src, title, link in n[:2]:
                msg.append(f"• [{src}] {cz(title)}")
                if link:
                    msg.append(link)
        telegram_send_long("\n".join(msg))

        cache[dkey][key] = True

    alerts_save(cache)


# ============================================================
# EMAIL: 1× denně (posíláme z PREMARKET reportu)
# ============================================================
def maybe_send_daily_email(report_text: str, charts: list):
    if not EMAIL_ENABLED:
        return
    d = today_str()
    last = read_text(LAST_EMAIL_DATE_FILE, "")
    if last == d:
        return
    subject = f"XTB Radar – denní report ({d})"
    email_send(subject, report_text, image_paths=charts)
    write_text(LAST_EMAIL_DATE_FILE, d)


# ============================================================
# BACKFILL (2025–2026…)
# ============================================================
def backfill_one_ticker(ticker: str, start: str, end: str):
    t = resolve_symbol(ticker)
    try:
        df = yf.download(t, start=start, end=end, interval="1d", progress=False, auto_adjust=False, threads=False)
        if df is None or df.empty:
            return False
        out_path = os.path.join(HISTORY_DIR, f"{ticker}.csv")
        df.to_csv(out_path)
        return True
    except Exception:
        return False

def run_backfill():
    end = BACKFILL_END.strip()
    if not end:
        end = today_str()
    ok = 0
    total = len(ALL_TICKERS)
    for t in ALL_TICKERS:
        if backfill_one_ticker(t, BACKFILL_START, end):
            ok += 1
    telegram_send(f"📚 BACKFILL hotový: {ok}/{total} tickerů | {BACKFILL_START} → {end}")


# ============================================================
# LEARN (1× týdně) – jednoduché přeladění vah
# ============================================================
def run_learn():
    """
    Jednoduchý “soft learning”:
    - vezmeme posledních N snapshotů (evening)
    - zkusíme upřednostnit složky, které v průměru korelují s 1D momentum (proxy)
    Není to ML, ale stabilní adaptace bez rozbití.
    """
    # načti posledních 40 řádků snapshots
    if not os.path.exists(SNAPSHOTS_FILE):
        telegram_send("ℹ️ Learn: žádné snapshoty zatím nejsou.")
        return

    rows = []
    try:
        with open(SNAPSHOTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(line)
    except Exception:
        rows = []

    if not rows:
        telegram_send("ℹ️ Learn: snapshot soubor je prázdný.")
        return

    tail = rows[-40:]
    snaps = []
    for line in tail:
        try:
            snaps.append(json.loads(line))
        except Exception:
            pass

    if not snaps:
        telegram_send("ℹ️ Learn: nešlo parsovat snapshoty.")
        return

    # hrubá heuristika: pokud RS5D a Catalyst častěji doprovází vyšší score, mírně posílit
    # (v praxi: spočteme průměr RS5D a počet news pro top kvantil)
    rs_vals = []
    vol_vals = []
    earn_vals = []
    for s in snaps:
        items = s.get("items", [])
        for it in items:
            rs = it.get("rs5d")
            volr = it.get("volr")
            ed = it.get("earn_days")
            if isinstance(rs, (int, float)):
                rs_vals.append(float(rs))
            if isinstance(volr, (int, float)):
                vol_vals.append(float(volr))
            if isinstance(ed, (int, float)):
                earn_vals.append(float(ed))

    # základ
    w = dict(DEFAULT_WEIGHTS)

    # úpravy: pokud je průměr RS kladný (outperformance), posil RS; pokud volr často >1.2, posil vol; earnings blízké => posil catalyst
    rs_mean = sum(rs_vals) / len(rs_vals) if rs_vals else 0.0
    vol_mean = sum(vol_vals) / len(vol_vals) if vol_vals else 1.0
    earn_mean = sum(earn_vals) / len(earn_vals) if earn_vals else 30.0

    if rs_mean > 0.3:
        w["rel_strength"] += 0.03
        w["momentum"] -= 0.01

    if vol_mean > 1.2:
        w["volatility_volume"] += 0.02
        w["momentum"] -= 0.01

    if earn_mean < 14:
        w["catalyst"] += 0.03
        w["market_regime"] -= 0.01

    # normalize + save
    ssum = sum(max(0.0, float(v)) for v in w.values())
    if ssum <= 0:
        w = dict(DEFAULT_WEIGHTS)
        ssum = sum(w.values())

    for k in w:
        w[k] = max(0.01, float(w[k]))
    ssum = sum(w.values())
    for k in w:
        w[k] = w[k] / ssum

    write_json(LEARNED_WEIGHTS_FILE, w)
    telegram_send(
        "🧠 Weekly learn hotový. Nové váhy:\n" +
        "\n".join([f"- {k}: {v:.3f}" for k, v in w.items()])
    )


# ============================================================
# MAIN MODE: run
# ============================================================
def maybe_premarket():
    d = today_str()
    last = read_text(LAST_PREMARKET_DATE_FILE, "")
    if last == d:
        return False
    if hm(now_local()) < PREMARKET_TIME:
        return False

    report = build_premarket_report()
    telegram_send_long(report)

    # email 1× denně – z premarket reportu + grafy top movers v portfoliu
    charts = []
    # grafy z portfolia (max 3)
    if plt is not None:
        for t in PORTFOLIO[:3]:
            fn = make_price_chart(t, days=30)
            if fn:
                charts.append(fn)

    maybe_send_daily_email(report, charts)

    write_text(LAST_PREMARKET_DATE_FILE, d)
    return True

def maybe_evening():
    d = today_str()
    last = read_text(LAST_EVENING_DATE_FILE, "")
    if last == d:
        return False
    if hm(now_local()) < EVENING_TIME:
        return False

    report, best, worst, new_sorted = build_evening_summary()
    telegram_send_long(report)

    # do email posíláme už jen 1× denně (pre-market), evening je telegram only
    write_text(LAST_EVENING_DATE_FILE, d)
    return True

def run_once():
    # 1) reporty podle času
    maybe_premarket()
    maybe_evening()

    # 2) alerty – když jsme v okně, běží každý run (GitHub spouští každých 15 min)
    alerts_check_and_send()


def main():
    print(f"✅ Bot start | mode={RUN_MODE} | tz={TZ_NAME} | now={now_local().isoformat()}")
    print("Secrets check:",
          "TG_TOKEN:", bool(TELEGRAM_TOKEN),
          "CHAT_ID:", bool(CHAT_ID),
          "FMP:", bool(FMP_API_KEY or cfg_get("fmp_api_key", "")),
          "EMAIL_ENABLED:", EMAIL_ENABLED,
          "EMAIL_SENDER:", bool(EMAIL_SENDER),
          "EMAIL_RECEIVER:", bool(EMAIL_RECEIVER),
    )

    if RUN_MODE == "backfill":
        run_backfill()
        return

    if RUN_MODE == "learn":
        run_learn()
        return

    # default: run
    run_once()
    print("✅ Done.")


if __name__ == "__main__":
    main()