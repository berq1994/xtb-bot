import os
import json
import math
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

TELEGRAM_TOKEN = (os.getenv("TELEGRAMTOKEN") or "").strip()
CHAT_ID = str(os.getenv("CHATID") or "").strip()
FMP_API_KEY = (os.getenv("FMPAPIKEY") or "").strip()

EMAIL_ENABLED = (os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true")
EMAIL_SENDER = (os.getenv("EMAIL_SENDER") or "").strip()
EMAIL_RECEIVER = (os.getenv("EMAIL_RECEIVER") or "").strip()
GMAILPASSWORD = (os.getenv("GMAILPASSWORD") or "").strip()

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
# PORTFOLIO / WATCHLIST / UNIVERSE
# ============================================================
PORTFOLIO = [
    "CENX","S","NVO","PYPL","AMZN","MSFT","CVX","NVDA","TSM","CAG","META","AAPL","GOOGL","TSLA",
    "PLTR","SPY","FCX","IREN"
]

# Watchlist pro best/worst
WATCHLIST = sorted(set(PORTFOLIO + [
    "AMD","ASML","AVGO","MU","ARM","QCOM","SMCI","INTC","TXN","ADI","MRVL","KLAC","LRCX","AMAT",
    "BHP","RIO","SCCO","AA","TECK","VALE","ALB","LAC","URNM","URA","CCJ"
]))

# Kandidáti pro „nové nadějné“ (mimo watchlist/portfolio)
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

LAST_EMAIL_DATE_FILE = os.path.join(STATE_DIR, "last_email_date.txt")
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
    except:
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
    except:
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
    except:
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
        print("⚠️ Telegram není nastaven: chybí TELEGRAMTOKEN/CHATID.")
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
# EMAIL (Gmail SMTP) – 1× denně (z 12:00 reportu)
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
    if not FMP_API_KEY:
        return None
    url = f"https://financialmodelingprep.com/api/{path}"
    p = dict(params or {})
    p["apikey"] = FMP_API_KEY
    try:
        r = requests.get(url, params=p, timeout=25)
        if r.status_code != 200:
            return None
        return r.json()
    except:
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
        except:
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
    except:
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
    except:
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
    except:
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
        except:
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
    - VIX (pokud jde) a 5D změna
    Výstup: (label, detail)
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
                # pokud VIX roste hodně, tlačí to do risk-off
                if v_ch > 10:
                    label = "RISK-OFF"
                elif v_ch < -10 and label != "RISK-OFF":
                    label = "RISK-ON"
    except:
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
    except:
        return None

def rel_strength_5d(ticker: str):
    r_t = ret_5d_yahoo(ticker)
    r_s = ret_5d_yahoo("SPY")
    if r_t is None or r_s is None:
        return None
    return r_t - r_s  # kladné = outperformuje SPY


# ============================================================
# SCORE (PROFI RADAR): pohyb + objem + zprávy + earnings + RS vs SPY
# ============================================================
W_MOVE = 1.0
W_VOL  = 0.7
W_NEWS = 0.4
W_EARN = 0.6
W_RS   = 0.6

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
    if rs is None:
        return 0.0
    # škálování: 0..+5 => 0..3, -5..0 => 0..1 (negativní RS penalizujeme)
    if rs >= 0:
        return clamp(rs / 5.0 * 3.0, 0, 3)
    return clamp(1.0 - abs(rs) / 10.0, 0, 1)

def compute_score(move_abs, vol_spike, news_count, earn_days, rs):
    return (
        W_MOVE * clamp(move_abs, 0, 10) +
        W_VOL  * clamp(vol_spike, 0, 5) +
        W_NEWS * clamp(float(news_count), 0, 6) +
        W_EARN * clamp(earnings_score(earn_days), 0, 3) +
        W_RS   * clamp(rs_score(rs), 0, 3)
    )

def score_explain(move_abs, vol_spike, news_count, earn_days, rs):
    parts = []
    if move_abs >= 4:
        parts.append("silný pohyb ceny")
    elif move_abs >= 2:
        parts.append("výraznější pohyb ceny")
    else:
        parts.append("menší pohyb ceny")

    if vol_spike >= 1.8:
        parts.append("výrazně vyšší objem")
    elif vol_spike >= 1.2:
        parts.append("vyšší objem")
    else:
        parts.append("objem bez spike")

    if news_count >= 5:
        parts.append("hodně zpráv")
    elif news_count >= 2:
        parts.append("několik zpráv")
    else:
        parts.append("málo zpráv")

    if rs is not None:
        parts.append(f"RS vs SPY (5D): {rs:+.2f} p.b.")

    if earn_days is not None:
        if earn_days <= 2:
            parts.append("earnings velmi blízko")
        elif earn_days <= 7:
            parts.append("earnings do týdne")
        elif earn_days <= 14:
            parts.append("earnings do 2 týdnů")

    return ", ".join(parts) + "."

def classify_opportunity(change_pct, vol_spike, news_items, rs):
    """
    Jednoduchá klasifikace (praktická):
    - Catalyst / News play
    - Breakout / Momentum
    - Mean reversion / výprodej
    - Low conviction move
    """
    news = len(news_items) > 0
    if news and abs(change_pct or 0) >= 2:
        return "Katalyzátor (zprávy)"
    if (change_pct or 0) > 3 and vol_spike >= 1.2:
        return "Momentum / možný breakout"
    if (change_pct or 0) < -3 and vol_spike >= 1.2:
        return "Výprodej / mean reversion kandidát"
    if rs is not None and rs > 1.5:
        return "Relativní síla (outperformuje SPY)"
    return "Neutrální / slabší signál"


# ============================================================
# GRAF do emailu
# ============================================================
def make_change_chart(changes: dict, file_path: str):
    tickers = list(changes.keys())
    values = [changes[t] for t in tickers]
    plt.figure(figsize=(10, 5))
    plt.bar(tickers, values)
    plt.axhline(0, linewidth=1)
    plt.title("Změna % (poslední close vs předchozí close)")
    plt.xlabel("Ticker")
    plt.ylabel("%")
    plt.tight_layout()
    plt.savefig(file_path)
    plt.close()


# ============================================================
# ALERTY – anti-spam (neposílat stejný alert pořád)
# ============================================================
def should_send_alert(ticker: str, change_open: float) -> bool:
    last = read_json(LAST_ALERTS_FILE, {})
    last_val = last.get(ticker)
    if last_val is None:
        return True
    # posun o aspoň 1 p.b. (proti spamu)
    return abs(change_open - last_val) >= 1.0

def mark_alert(ticker: str, change_open: float):
    last = read_json(LAST_ALERTS_FILE, {})
    last[ticker] = change_open
    write_json(LAST_ALERTS_FILE, last)


# ============================================================
# 12:00 REPORT (Telegram + Email 1× denně)
# ============================================================
def premarket_job():
    now = now_local()
    if hm(now) != PREMARKET_TIME:
        return
    if read_text(LAST_PREMARKET_DATE_FILE, "") == today_str():
        return

    regime, regime_detail = market_regime()

    rows = []
    earnings_today, earnings_tom = [], []
    today_d = date.today()
    tom_d = today_d + timedelta(days=1)

    for t in PORTFOLIO:
        last, prev, src = daily_last_prev(t)
        if last is None:
            continue
        ch = pct_change(last, prev)

        ed = fmp_next_earnings_date(t)
        if ed == today_d:
            earnings_today.append(t)
        elif ed == tom_d:
            earnings_tom.append(t)

        prof = get_profile(t)
        rows.append((t, prof, last, ch, src))

    rows.sort(key=lambda x: abs(x[3]) if x[3] is not None else -1, reverse=True)

    msg = []
    msg.append(f"🕛 REPORT 12:00 ({now.strftime('%d.%m.%Y %H:%M')})")
    msg.append(f"Režim trhu: {regime} | {regime_detail}")
    msg.append("⚠️ Informativní přehled (nejde o investiční doporučení).")
    msg.append("")
    if earnings_today:
        msg.append("📣 Earnings DNES: " + ", ".join(earnings_today))
    if earnings_tom:
        msg.append("⏰ Earnings ZÍTRA: " + ", ".join(earnings_tom))
    msg.append("")

    msg.append("📌 Největší denní pohyby (close vs předchozí close):")
    for t, prof, last, ch, src in rows[:12]:
        nm = prof.get("name") or t
        sector = (prof.get("sector") or "").strip()
        sec_txt = f" [{sector}]" if sector else ""
        if ch is None:
            msg.append(f"• {t} — {nm}{sec_txt}: {last:.2f} (n/a) ({src})")
        else:
            sign = "🟩" if ch >= 0 else "🟥"
            msg.append(f"• {sign} {t} — {nm}{sec_txt}: {last:.2f} ({ch:+.2f}%) {bar(ch)} ({src})")

        news = combined_news(t, 1)
        if news:
            srcN, titleN, _ = news[0]
            msg.append(f"   📰 {srcN}: {cz(titleN)}")

    telegram_send_long("\n".join(msg))
    write_text(LAST_PREMARKET_DATE_FILE, today_str())

    # Email max 1× denně (z 12:00 reportu)
    if EMAIL_ENABLED and read_text(LAST_EMAIL_DATE_FILE, "") != today_str():
        changes = {}
        for t, prof, last, ch, src in rows:
            if ch is not None:
                changes[t] = ch

        chart_path = os.path.join(STATE_DIR, f"denni_zmena_{today_str()}.png")
        images = []
        try:
            make_change_chart(dict(list(changes.items())[:16]), chart_path)
            images = [chart_path]
        except Exception as e:
            print("Chart error:", e)

        body = []
        body.append(f"REPORT 12:00 ({now.strftime('%d.%m.%Y %H:%M')} – {TZ_NAME})")
        body.append(f"Režim trhu: {regime} | {regime_detail}")
        body.append("Zdroj cen: FMP primárně, fallback Yahoo.")
        body.append("")
        if earnings_today:
            body.append("Earnings DNES: " + ", ".join(earnings_today))
        if earnings_tom:
            body.append("Earnings ZÍTRA: " + ", ".join(earnings_tom))
        body.append("")
        body.append("Top pohyby:")
        for t, prof, last, ch, src in rows[:15]:
            nm = prof.get("name") or t
            sector = (prof.get("sector") or "").strip()
            sec_txt = f" [{sector}]" if sector else ""
            if ch is None:
                body.append(f"- {t} — {nm}{sec_txt} | {last:.2f} | n/a | {src}")
            else:
                emoji = "🟩" if ch >= 0 else "🟥"
                body.append(f"- {emoji} {t} — {nm}{sec_txt} | {last:.2f} | {ch:+.2f}% | {src}")

        body.append("")
        body.append("Novinky (FMP + Yahoo RSS + SeekingAlpha RSS + Google News):")
        for t, prof, last, ch, src in rows[:8]:
            news = combined_news(t, NEWS_PER_TICKER)
            if not news:
                continue
            nm = prof.get("name") or t
            body.append(f"\n{t} — {nm}")
            for sN, titleN, linkN in news[:NEWS_PER_TICKER]:
                title_cs = cz(titleN)
                if linkN:
                    body.append(f"  • ({sN}) {title_cs} — {linkN}")
                else:
                    body.append(f"  • ({sN}) {title_cs}")

        email_send(
            subject=f"📧 Report 12:00 – {now.strftime('%d.%m.%Y')}",
            body_text="\n".join(body),
            image_paths=images
        )
        write_text(LAST_EMAIL_DATE_FILE, today_str())


# ============================================================
# ALERTY 12–21 (každý run = každých 15 min) – % od OPEN
# ============================================================
def alerts_job():
    now = now_local()
    now_hm = hm(now)
    if not in_window(now_hm, ALERT_START, ALERT_END):
        return
    if OPPORTUNITY_WEEKDAYS_ONLY and not is_weekday(now):
        return

    regime, regime_detail = market_regime()

    for t in PORTFOLIO:
        intr = intraday_open_last_yahoo(t)
        if not intr:
            continue
        o, last = intr
        ch = pct_change(last, o)
        if ch is None or abs(ch) < ALERT_THRESHOLD:
            continue
        if not should_send_alert(t, ch):
            continue

        prof = get_profile(t)
        name = prof.get("name") or t
        sector = (prof.get("sector") or "").strip()
        sec_txt = f" [{sector}]" if sector else ""

        sign = "🟩" if ch >= 0 else "🟥"
        arrow = "📈" if ch >= 0 else "📉"

        news = combined_news(t, 2)
        why = why_from_headlines(news)
        rs = rel_strength_5d(t)
        vol_sp = volume_spike_yahoo(t)

        typ = classify_opportunity(ch, vol_sp, news, rs)

        msg = []
        msg.append(f"🚨 ALERT {sign} {t} ({now_hm})")
        msg.append(f"{name}{sec_txt}")
        msg.append(f"Změna od dnešního OPEN: {ch:+.2f}% {arrow} {bar(ch)}")
        msg.append(f"Aktuální cena: {last:.2f}")
        if rs is not None:
            msg.append(f"Relativní síla vs SPY (5D): {rs:+.2f} p.b.")
        msg.append(f"Typ signálu: {typ}")
        msg.append(f"Režim trhu: {regime}")
        msg.append(f"Možný důvod (z titulků): {why}")
        if news:
            srcN, titleN, _ = news[0]
            msg.append(f"Top zpráva: [{srcN}] {cz(titleN)}")

        telegram_send("\n".join(msg))
        mark_alert(t, ch)


# ============================================================
# VEČERNÍ RADAR 20:00 (Best / Worst / New) – PRO verze
# ============================================================
def short_desc(desc: str, max_len: int = 240) -> str:
    if not desc:
        return ""
    d = desc.strip().replace("\n", " ")
    if len(d) <= max_len:
        return d
    return d[:max_len].rstrip() + "…"

def build_scored_list(tickers: list[str]):
    rows = []
    for t in tickers:
        last, prev, src = daily_last_prev(t)
        if last is None:
            continue
        ch = pct_change(last, prev)
        move_abs = abs(ch) if ch is not None else 0.0

        vol_spike = volume_spike_yahoo(t)
        news_items = combined_news(t, NEWS_PER_TICKER)
        news_count = len(news_items)

        edays = days_to_earnings(t)
        rs = rel_strength_5d(t)

        score = compute_score(move_abs, vol_spike, news_count, edays, rs)

        prof = get_profile(t)

        rows.append({
            "ticker": t,
            "name": prof.get("name") or t,
            "sector": (prof.get("sector") or "").strip(),
            "industry": (prof.get("industry") or "").strip(),
            "desc": (prof.get("description") or "").strip(),
            "last": last,
            "ch": ch,
            "score": score,
            "vol_spike": vol_spike,
            "news_items": news_items,
            "why": why_from_headlines(news_items),
            "earn_days": edays,
            "rs": rs,
            "src": src
        })
    return rows

def evening_job():
    now = now_local()
    if hm(now) != EVENING_TIME:
        return
    if read_text(LAST_EVENING_DATE_FILE, "") == today_str():
        return
    if OPPORTUNITY_WEEKDAYS_ONLY and not is_weekday(now):
        return

    regime, regime_detail = market_regime()

    wl_rows = build_scored_list(WATCHLIST)
    if not wl_rows:
        telegram_send("⚠️ Večerní radar: nepodařilo se načíst data (FMP/Yahoo).")
        return

    # Best/Worst podle score (radar)
    wl_sorted = sorted(wl_rows, key=lambda r: r["score"], reverse=True)
    best = wl_sorted[:OPPORTUNITY_MAX]
    worst = list(reversed(wl_sorted[-OPPORTUNITY_MAX:]))

    # New opportunities: kandidáti mimo watchlist/portfolio
    exclude = set(WATCHLIST) | set(PORTFOLIO)
    new_candidates = [t for t in CANDIDATE_UNIVERSE if t not in exclude]
    new_rows = build_scored_list(new_candidates)
    new_sorted = sorted(new_rows, key=lambda r: r["score"], reverse=True)[:OPPORTUNITY_MAX]

    msg = []
    msg.append(f"🕗 INVESTIČNÍ RADAR (20:00) – {now.strftime('%d.%m.%Y %H:%M')}")
    msg.append(f"Režim trhu: {regime} | {regime_detail}")
    msg.append("⚠️ Informativní přehled (nejde o investiční doporučení).")
    msg.append("")

    msg.append(f"🟢 TOP {OPPORTUNITY_MAX} nejsilnější (WATCHLIST) – podle radar SCORE")
    msg.append("SCORE = pohyb + objem + zprávy + blízkost earnings + relativní síla vs SPY.")
    msg.append("")
    for r in best:
        ch = r["ch"]
        sec_txt = f" [{r['sector']}]" if r["sector"] else ""
        emoji = "🟩" if (ch is not None and ch >= 0) else "🟥"
        arrow = "📈" if (ch is not None and ch >= 0) else "📉"
        head = f"{emoji} {arrow} {r['ticker']} — {r['name']}{sec_txt} | {r['last']:.2f}"
        if ch is not None:
            head += f" ({ch:+.2f}%) {bar(ch)}"
        head += f" | SCORE {r['score']:.2f}"
        msg.append(head)

        msg.append(f"• Proč v TOP: {score_explain(abs(ch) if ch else 0.0, r['vol_spike'], len(r['news_items']), r['earn_days'], r['rs'])}")
        note = earnings_note(r["earn_days"])
        if note:
            msg.append(f"• Riziko: {note}")
        msg.append(f"• Typ: {classify_opportunity(ch or 0.0, r['vol_spike'], r['news_items'], r['rs'])}")
        msg.append(f"• Možný důvod: {r['why']}")
        if r["desc"]:
            msg.append(f"• Co firma dělá: {cz(short_desc(r['desc']))}")
        if r["news_items"]:
            srcN, titleN, _ = r["news_items"][0]
            msg.append(f"• Top zpráva: [{srcN}] {cz(titleN)}")
        msg.append("")

    msg.append(f"🔴 TOP {OPPORTUNITY_MAX} nejslabší (WATCHLIST) – podle radar SCORE (nejnižší)")
    msg.append("")
    for r in worst:
        ch = r["ch"]
        sec_txt = f" [{r['sector']}]" if r["sector"] else ""
        emoji = "🟥" if (ch is not None and ch < 0) else "🟩"
        arrow = "📉" if (ch is not None and ch < 0) else "📈"
        head = f"{emoji} {arrow} {r['ticker']} — {r['name']}{sec_txt} | {r['last']:.2f}"
        if ch is not None:
            head += f" ({ch:+.2f}%) {bar(ch)}"
        head += f" | SCORE {r['score']:.2f}"
        msg.append(head)

        msg.append(f"• Proč v BOTTOM: {score_explain(abs(ch) if ch else 0.0, r['vol_spike'], len(r['news_items']), r['earn_days'], r['rs'])}")
        note = earnings_note(r["earn_days"])
        if note:
            msg.append(f"• Riziko: {note}")
        msg.append(f"• Typ: {classify_opportunity(ch or 0.0, r['vol_spike'], r['news_items'], r['rs'])}")
        msg.append(f"• Možný důvod: {r['why']}")
        if r["news_items"]:
            srcN, titleN, _ = r["news_items"][0]
            msg.append(f"• Top zpráva: [{srcN}] {cz(titleN)}")
        msg.append("")

    msg.append(f"🆕 TOP {OPPORTUNITY_MAX} nové nadějné (mimo WATCHLIST i PORTFOLIO)")
    msg.append("Cíl: shortlist k prověření (ne automatické nákupní doporučení).")
    msg.append("")
    if not new_sorted:
        msg.append("• Dnes žádní kandidáti nevyšli podle scoringu.")
    else:
        for r in new_sorted:
            ch = r["ch"]
            sec_txt = f" [{r['sector']}]" if r["sector"] else ""
            arrow = "📈" if (ch is not None and ch >= 0) else "📉"
            head = f"{arrow} {r['ticker']} — {r['name']}{sec_txt} | {r['last']:.2f}"
            if ch is not None:
                head += f" ({ch:+.2f}%) {bar(ch)}"
            head += f" | SCORE {r['score']:.2f}"
            msg.append(head)

            msg.append(f"• Proč je zajímavá: {score_explain(abs(ch) if ch else 0.0, r['vol_spike'], len(r['news_items']), r['earn_days'], r['rs'])}")
            msg.append(f"• Typ: {classify_opportunity(ch or 0.0, r['vol_spike'], r['news_items'], r['rs'])}")
            if r["desc"]:
                msg.append(f"• Co firma dělá: {cz(short_desc(r['desc']))}")
            if r["news_items"]:
                srcN, titleN, _ = r["news_items"][0]
                msg.append(f"• Top zpráva: [{srcN}] {cz(titleN)}")
            msg.append("")

    telegram_send_long("\n".join(msg))
    write_text(LAST_EVENING_DATE_FILE, today_str())


# ============================================================
# MAIN (GitHub Actions: jeden běh = jeden „tick“)
# ============================================================
def main():
    # 12:00 report + email
    premarket_job()

    # alerty 12–21 (každých 15 min podle cron)
    alerts_job()

    # 20:00 radar
    evening_job()

    print("✅ Hotovo:", now_local().strftime("%d.%m.%Y %H:%M"))

if __name__ == "__main__":
    main()
