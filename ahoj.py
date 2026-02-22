import os
import json
import math
import time
import requests
import feedparser
import yfinance as yf
import matplotlib.pyplot as plt

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Email (Gmail SMTP)
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# YAML (config)
try:
    import yaml
except Exception:
    yaml = None


# ============================================================
# PŘEKLADY (vše do češtiny)
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
        return _TRANATE_CACHE[key]  # typo guard? (kept safe below)
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


# Fix for possible typo in cache key access above
def _cz(text: str) -> str:
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
        out = _TRANSLATOR.translate(key)
        _TRANSLATE_CACHE[key] = out
        return out
    except Exception:
        _TRANSLATE_CACHE[key] = key
        return key


# ============================================================
# ENV / NASTAVENÍ
# ============================================================
TZ_NAME = os.getenv("TIMEZONE", "Europe/Prague").strip()
TZ = ZoneInfo(TZ_NAME)

TELEGRAM_TOKEN = (os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
CHAT_ID = str(os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or "").strip()
FMP_API_KEY = (os.getenv("FMPAPIKEY") or os.getenv("FMP_API_KEY") or "").strip()

EMAIL_ENABLED = (os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true")
EMAIL_SENDER = (os.getenv("EMAIL_SENDER") or "").strip()
EMAIL_RECEIVER = (os.getenv("EMAIL_RECEIVER") or "").strip()
GMAILPASSWORD = (os.getenv("GMAILPASSWORD") or "").strip()

# časy reportů (lokální TZ)
PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()

ALERT_START = os.getenv("ALERT_START", "12:00").strip()
ALERT_END = os.getenv("ALERT_END", "21:00").strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3").strip())  # % od dnešního OPEN

NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2").strip())
OPPORTUNITY_MAX = int(os.getenv("OPPORTUNITY_MAX", "5").strip())
OPPORTUNITY_WEEKDAYS_ONLY = (os.getenv("OPPORTUNITY_WEEKDAYS_ONLY", "true").lower().strip() == "true")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ============================================================
# CONFIG (YAML) – pokud máš config.yml
# ============================================================
DEFAULT_CONFIG_PATHS = [
    "config.yml",
    "config.yaml",
    ".github/config.yml",
    ".github/config.yaml",
]

def load_cfg():
    """
    Načte config.yml pokud existuje.
    Pokud YAML chybí (knihovna nebo soubor), vrátí {}.
    """
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
    """
    Bezpečné čtení z CFG podle path jako:
    "telegram.bot_token" / "weights.momentum" / "portfolio"
    """
    try:
        cur = CFG
        for part in path.split("."):
            if not isinstance(cur, dict):
                return default
            cur = cur.get(part)
        return default if cur is None else cur
    except Exception:
        return default


# ============================================================
# PORTFOLIO / WATCHLIST / UNIVERSE
# ============================================================
# Pokud je portfolio v configu, použijeme ho. Jinak fallback.
def portfolio_from_cfg():
    items = cfg_get("portfolio", [])
    out = []
    if isinstance(items, list):
        for row in items:
            if isinstance(row, dict) and row.get("ticker"):
                out.append(row.get("ticker").strip().upper())
    return out

PORTFOLIO = portfolio_from_cfg()
if not PORTFOLIO:
    PORTFOLIO = [
        "CENX","S","NVO","PYPL","AMZN","MSFT","CVX","NVDA","TSM","CAG","META","AAPL","GOOGL","TSLA",
        "PLTR","SPY","FCX","IREN"
    ]

# Watchlist pro best/worst
WATCHLIST_CFG = cfg_get("watchlist", [])
WATCHLIST = []
if isinstance(WATCHLIST_CFG, list) and WATCHLIST_CFG:
    WATCHLIST = sorted(set([str(x).strip().upper() for x in WATCHLIST_CFG] + PORTFOLIO))
else:
    WATCHLIST = sorted(set(PORTFOLIO + [
        "AMD","ASML","AVGO","MU","ARM","QCOM","SMCI","INTC","TXN","ADI","MRVL","KLAC","LRCX","AMAT",
        "BHP","RIO","SCCO","AA","TECK","VALE","ALB","LAC","URNM","URA","CCJ"
    ]))

# Kandidáti pro „nové nadějné“ (mimo watchlist/portfolio)
# !!! TADY BYLA TVOJE CHYBA: new_candidates může být omylem bool.
def new_candidates_from_cfg():
    raw = cfg_get("new_candidates", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        # když YAML omylem obsahuje true/false apod.
        raw = []
    out = []
    for x in raw:
        out.append(str(x).strip().upper())
    return [x for x in out if x]

CANDIDATE_UNIVERSE = new_candidates_from_cfg()
if not CANDIDATE_UNIVERSE:
    CANDIDATE_UNIVERSE = [
        # AI / software / data
        "SNOW","DDOG","MDB","NET","CRWD","ZS","PANW","NOW","ADBE","ORCL",
        # Semis / infra
        "ON","MPWR","ANET","DELL","HPE",
        # Metals / mining / energy proxy
        "NUE","STLD","GOLD","AEM","WPM","GLD","SLV",
        # Uranium / energy
        "UUUU","UEC","SMR","OKLO"
    ]


# ============================================================
# STATE (cache přes GitHub Actions)
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_ALERTS_FILE = os.path.join(STATE_DIR, "last_alerts.json")
PROFILE_CACHE_FILE = os.path.join(STATE_DIR, "profiles.json")


# ============================================================
# UTIL
# ============================================================
def now_local() -> datetime:
    return datetime.now(TZ)

def today_str() -> str:
    return now_local().strftime("%Y-%m-%d")

def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")

def is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5

def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm

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
    """Textový bar pro +/- 0..10 % (čím víc, tím víc bloků)."""
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


# ============================================================
# TELEGRAM
# ============================================================
def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram není nastaven: chybí TELEGRAMTOKEN/CHATID nebo TG_BOT_TOKEN/TG_CHAT_ID.")
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
# EMAIL (Gmail SMTP) – volitelné
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
# FMP API
# ============================================================
def fmp_get(path: str, params=None):
    key = FMP_API_KEY or cfg_get("fmp_api_key", "")
    key = (key or "").strip()
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
# PROFIL FIRMY (celé jméno + popis)
# ============================================================
def profiles_cache_load():
    return read_json(PROFILE_CACHE_FILE, {})

def profiles_cache_save(cache):
    write_json(PROFILE_CACHE_FILE, cache)

def get_profile(ticker: str):
    cache = profiles_cache_load()
    if ticker in cache:
        return cache[ticker]

    prof = {"name": ticker, "sector": "", "industry": "", "description": ""}

    # FMP primárně
    data = fmp_get("v3/profile", {"symbol": ticker})
    if isinstance(data, list) and data:
        row = data[0]
        prof["name"] = (row.get("companyName") or ticker).strip()
        prof["sector"] = (row.get("sector") or "").strip()
        prof["industry"] = (row.get("industry") or "").strip()
        prof["description"] = (row.get("description") or "").strip()

    # Yahoo fallback
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
# CENY: daily (FMP primárně, Yahoo fallback)
# ============================================================
def prices_daily_fmp(ticker: str):
    data = fmp_get("v3/historical-price-full/" + ticker, {"serietype": "line", "timeseries": 5})
    if not isinstance(data, dict):
        return None
    hist = data.get("historical")
    if not isinstance(hist, list) or len(hist) < 2:
        return None
    c0 = safe_float(hist[0].get("close"))
    c1 = safe_float(hist[1].get("close"))
    if c0 is None or c1 is None:
        return None
    return c0, c1

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

def daily_last_prev(ticker: str):
    got = prices_daily_fmp(ticker)
    if got:
        return got[0], got[1], "FMP"
    got = prices_daily_yahoo(ticker)
    if got:
        return got[0], got[1], "Yahoo"
    return None, None, "—"


# ============================================================
# INTRADAY pro alerty (Yahoo 5m)
# ============================================================
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
# NEWS: FMP + RSS (Yahoo + SeekingAlpha + Google)
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
# EARNINGS: FMP kalendář (kdy je nejbližší)
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
# MARKET REŽIM (Risk-On / Risk-Off) + kontext
# ============================================================
def market_regime():
    """
    Heuristika:
    - SPY 20D trend (+/-)
    - VIX 5D změna
    """
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

    return label, "; ".join(detail) if detail else "Bez dostatečných dat (fallback režim)."


# ============================================================
# RELATIVNÍ SÍLA vs SPY (5D)
# ============================================================
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

def rel_strength_5d(ticker: str):
    r_t = ret_5d_yahoo(ticker)
    r_s = ret_5d_yahoo("SPY")
    if r_t is None or r_s is None:
        return None
    return r_t - r_s  # kladné = outperformuje SPY


# ============================================================
# SCORE (PRO RADAR): momentum + objem + zprávy + earnings + RS + režim
# ============================================================
WEIGHTS = {
    "momentum": float(cfg_get("weights.momentum", 0.25)),
    "rel_strength": float(cfg_get("weights.rel_strength", 0.20)),
    "volatility_volume": float(cfg_get("weights.volatility_volume", 0.15)),
    "catalyst": float(cfg_get("weights.catalyst", 0.20)),
    "market_regime": float(cfg_get("weights.market_regime", 0.20)),
}

ADVICE_MODE = str(cfg_get("advice_mode", "SOFT")).strip().upper()
if ADVICE_MODE not in ("SOFT", "HARD"):
    ADVICE_MODE = "SOFT"

def momentum_score_1d(pct1d):
    if pct1d is None:
        return 0.0
    a = abs(pct1d)
    # 0..8% -> 0..10
    return clamp((a / 8.0) * 10.0, 0.0, 10.0)

def vol_score(vol_ratio):
    # 1.0 = normál, 2.0 = velký spike
    if vol_ratio is None:
        return 0.0
    return clamp((vol_ratio - 1.0) * 6.0, 0.0, 10.0)

def catalyst_score(news_items, days_earn):
    s = 0.0
    # news: max 4
    if news_items and len(news_items) > 0:
        s += min(4.0, 1.0 + 0.7 * len(news_items))
    # earnings: max 6
    if days_earn is not None:
        if days_earn <= 2:
            s += 6.0
        elif days_earn <= 7:
            s += 4.0
        elif days_earn <= 14:
            s += 2.0
    return clamp(s, 0.0, 10.0)

def rs_score(rs):
    # rs +5% -> 10, rs 0 -> 5, rs -5 -> 0
    if rs is None:
        return 0.0
    return clamp((rs + 5.0) * 1.0, 0.0, 10.0)

def regime_score(regime_label):
    # risk-on = 10, neutral = 5, risk-off = 0
    if regime_label == "RISK-ON":
        return 10.0
    if regime_label == "RISK-OFF":
        return 0.0
    return 5.0

def total_score(mom, rs, vol, cat, reg):
    return (
        WEIGHTS["momentum"] * mom +
        WEIGHTS["rel_strength"] * rs +
        WEIGHTS["volatility_volume"] * vol +
        WEIGHTS["catalyst"] * cat +
        WEIGHTS["market_regime"] * reg
    )

def hard_action_from_score(score, regime_label, days_earn):
    """
    HARD mode jednoduchá logika:
    - earnings do 48h -> WAIT
    - risk-off -> spíš HOLD/REDUCE
    - score >= 7.5 -> BUY (pokud ne risk-off)
    - score <= 3.0 -> SELL/REDUCE (pokud risk-off nebo slabé)
    """
    if days_earn is not None and days_earn <= int(cfg_get("risk_rules.earnings_wait_hours", 48)) // 24:
        return "WAIT"
    if regime_label == "RISK-OFF":
        if score >= 7.5:
            return "HOLD (strong, but risk-off)"
        if score <= 3.0:
            return "REDUCE"
        return "HOLD"
    # risk-on / neutral
    if score >= 7.5:
        return "BUY"
    if score <= 3.0:
        return "SELL/REDUCE"
    return "HOLD"

def format_ticker_line(ticker, pct1d, src, score, action, why, earn_note, vol_ratio, rs):
    pct_txt = "—" if pct1d is None else f"{pct1d:+.2f}% {bar(pct1d)}"
    vr_txt = f"{vol_ratio:.2f}×" if vol_ratio is not None else "—"
    rs_txt = f"{rs:+.2f}%" if rs is not None else "—"
    base = f"{ticker:>6}  {pct_txt}  | score {score:.2f}"
    if ADVICE_MODE == "HARD":
        base += f" | {action}"
    base += f"\n   RS(5D): {rs_txt} | Volume: {vr_txt} | Zdroj: {src}"
    if earn_note:
        base += f"\n   {earn_note}"
    if why:
        base += f"\n   Proč: {why}"
    return base

def build_radar_for_list(tickers, limit_news_each=NEWS_PER_TICKER):
    regime_label, regime_detail = market_regime()
    reg_s = regime_score(regime_label)

    rows = []
    for t in tickers:
        last, prev, src = daily_last_prev(t)
        pct1d = pct_change(last, prev)
        vr = volume_spike_yahoo(t)
        rs = rel_strength_5d(t)
        news_items = combined_news(t, limit_news_each)[:limit_news_each]
        why = why_from_headlines(news_items)
        d_earn = days_to_earnings(t)
        enote = earnings_note(d_earn)

        mom = momentum_score_1d(pct1d)
        vol = vol_score(vr)
        cat = catalyst_score(news_items, d_earn)
        rss = rs_score(rs)

        score = total_score(mom, rss, vol, cat, reg_s)
        action = hard_action_from_score(score, regime_label, d_earn)

        rows.append({
            "ticker": t,
            "pct1d": pct1d,
            "src": src,
            "score": score,
            "action": action,
            "why": why,
            "earn_note": enote,
            "vol_ratio": vr,
            "rs": rs,
        })

    # seřadíme podle score desc
    rows.sort(key=lambda x: x["score"], reverse=True)

    header = (
        f"📡 MEGA INVESTIČNÍ RADAR ({today_str()} {hm(now_local())})\n"
        f"Režim trhu: {regime_label} ({regime_detail})\n"
        f"Režim rad: {ADVICE_MODE}\n"
        f"Váhy: momentum {WEIGHTS['momentum']}, RS {WEIGHTS['rel_strength']}, vol/objem {WEIGHTS['volatility_volume']}, catalyst {WEIGHTS['catalyst']}, regime {WEIGHTS['market_regime']}\n"
        "—\n"
    )
    lines = [header]
    for r in rows:
        lines.append(format_ticker_line(
            r["ticker"], r["pct1d"], r["src"], r["score"], r["action"],
            r["why"], r["earn_note"], r["vol_ratio"], r["rs"]
        ))
        lines.append("")

    return "\n".join(lines).strip(), rows


# ============================================================
# ALERTY (intraday) – jen když se to hýbe o víc než threshold
# ============================================================
def load_last_alerts():
    return read_json(LAST_ALERTS_FILE, {})

def save_last_alerts(data):
    write_json(LAST_ALERTS_FILE, data)

def check_intraday_alerts():
    now = now_local()
    if OPPORTUNITY_WEEKDAYS_ONLY and (not is_weekday(now)):
        return

    nowhm = hm(now)
    if not in_window(nowhm, ALERT_START, ALERT_END):
        return

    last_alerts = load_last_alerts()
    todays = last_alerts.get(today_str(), {})

    hits = []
    for t in WATCHLIST:
        got = intraday_open_last_yahoo(t)
        if not got:
            continue
        o, last = got
        pct = pct_change(last, o)
        if pct is None:
            continue
        if abs(pct) >= ALERT_THRESHOLD:
            # ať nespamujeme: 1 ticker max 1× za den pro intraday alert
            if todays.get(t):
                continue
            todays[t] = True
            why = why_from_headlines(combined_news(t, 2)[:2])
            hits.append((t, pct, why))

    if hits:
        hits.sort(key=lambda x: abs(x[1]), reverse=True)
        msg = f"🚨 ALERT ({today_str()} {nowhm}) – pohyb od OPEN ≥ {ALERT_THRESHOLD:.1f}%\n"
        for t, pct, why in hits[:10]:
            msg += f"\n{t}: {pct:+.2f}% {bar(pct)}\nProč: {why}\n"
        telegram_send_long(msg.strip())

    last_alerts[today_str()] = todays
    save_last_alerts(last_alerts)


# ============================================================
# REPORTY (12:00 a 20:00)
# ============================================================
def should_run_once_per_day(marker_file: str, target_hm: str, tolerance_min: int = 10):
    """
    True pokud:
    - dnes ještě neběžel
    - a aktuální čas je v okně [target - tol, target + tol]
    """
    now = now_local()
    last = read_text(marker_file, "")
    if last == today_str():
        return False

    # okno
    try:
        th, tm = target_hm.split(":")
        target = now.replace(hour=int(th), minute=int(tm), second=0, microsecond=0)
    except Exception:
        target = now.replace(hour=12, minute=0, second=0, microsecond=0)

    delta = abs((now - target).total_seconds()) / 60.0
    return delta <= tolerance_min

def mark_ran(marker_file: str):
    write_text(marker_file, today_str())


def premarket_report():
    text, rows = build_radar_for_list(PORTFOLIO, limit_news_each=NEWS_PER_TICKER)

    # TOP shrnutí pro rychlost
    top = rows[:5]
    worst = sorted(rows, key=lambda x: x["score"])[:3]

    head = f"✅ PORTFOLIO REPORT (12:00) – {today_str()}\n"
    head += "TOP (score): " + ", ".join([f"{r['ticker']} {r['score']:.2f}" for r in top]) + "\n"
    head += "WEAK (score): " + ", ".join([f"{r['ticker']} {r['score']:.2f}" for r in worst]) + "\n"
    head += "—\n"

    telegram_send_long(head + text)

    # Volitelně email 1× denně (stejný report)
    if EMAIL_ENABLED:
        email_send(
            subject=f"Portfolio report {today_str()}",
            body_text=head + text
        )

def evening_report():
    # večer sledujeme WATCHLIST a “new candidates”
    tickers = sorted(set(WATCHLIST + CANDIDATE_UNIVERSE))
    text, rows = build_radar_for_list(tickers, limit_news_each=1)

    top = rows[:8]
    head = f"🌙 VEČERNÍ RADAR (20:00) – {today_str()}\n"
    head += "TOP: " + ", ".join([f"{r['ticker']} {r['score']:.2f}" for r in top]) + "\n"
    head += f"Kandidáti /new: {', '.join(CANDIDATE_UNIVERSE) if CANDIDATE_UNIVERSE else '—'}\n"
    head += "—\n"

    telegram_send_long(head + text)


# ============================================================
# MAIN
# ============================================================
def main():
    now = now_local()
    print("Now:", now.isoformat(), "TZ:", TZ_NAME)

    # Intraday alerty (každý běh workflow je může zkontrolovat)
    check_intraday_alerts()

    # 12:00 report 1× denně
    if should_run_once_per_day(LAST_PREMARKET_DATE_FILE, PREMARKET_TIME, tolerance_min=12):
        premarket_report()
        mark_ran(LAST_PREMARKET_DATE_FILE)

    # 20:00 report 1× denně
    if should_run_once_per_day(LAST_EVENING_DATE_FILE, EVENING_TIME, tolerance_min=12):
        evening_report()
        mark_ran(LAST_EVENING_DATE_FILE)


if __name__ == "__main__":
    main()
