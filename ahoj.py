import os
import json
import math
import time
import requests
import feedparser
import yfinance as yf

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import matplotlib.pyplot as plt


# =========================
# ENV / NASTAVENÍ
# =========================
TZ_NAME = os.getenv("TIMEZONE", "Europe/Prague").strip()
TZ = ZoneInfo(TZ_NAME)

TELEGRAM_TOKEN = os.getenv("TELEGRAMTOKEN", "").strip()
CHAT_ID = str(os.getenv("CHATID", "")).strip()
FMP_API_KEY = os.getenv("FMPAPIKEY", "").strip()

EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "").strip()
GMAILPASSWORD = os.getenv("GMAILPASSWORD", "").strip()

PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()

ALERT_START = os.getenv("ALERT_START", "12:00").strip()
ALERT_END = os.getenv("ALERT_END", "21:00").strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3").strip())  # %
NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2").strip())
OPPORTUNITY_MAX = int(os.getenv("OPPORTUNITY_MAX", "5").strip())
OPPORTUNITY_WEEKDAYS_ONLY = os.getenv("OPPORTUNITY_WEEKDAYS_ONLY", "true").lower().strip() == "true"

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# =========================
# PORTFOLIO (můžeš rozšířit)
# =========================
PORTFOLIO = [
    "CENX","S","NVO","PYPL","AMZN","MSFT","CVX","NVDA","TSM","CAG","META","AAPL","GOOGL","TSLA",
    "PLTR","SPY","FCX","IREN"
]

# Watchlist příležitostí (AI/čipy/kovy)
OPPORTUNITY_WATCHLIST = [
    "NVDA","TSM","ASML","AMD","AVGO","MU","ARM","QCOM","SMCI",
    "MSFT","AMZN","GOOGL",
    "FCX","RIO","BHP","SCCO","AA","CENX","TECK","PLTR","IREN"
]


# =========================
# STATE / CACHE
# =========================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

STATE_FILE = os.path.join(STATE_DIR, "state.json")
PROFILE_CACHE_FILE = os.path.join(STATE_DIR, "profiles.json")
LAST_EMAIL_DATE_FILE = os.path.join(STATE_DIR, "last_email_date.txt")
LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_ALERTS_FILE = os.path.join(STATE_DIR, "last_alerts.json")  # anti-spam


def now_local() -> datetime:
    return datetime.now(TZ)

def today_str() -> str:
    return now_local().strftime("%Y-%m-%d")

def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")

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

def is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5  # Po–Pá

def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    # stejné denní okno
    return start_hm <= now_hm <= end_hm

def clamp(x, lo=0.0, hi=10.0):
    return max(lo, min(hi, x))

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

def bar(pct: float, width: int = 14) -> str:
    if pct is None:
        return ""
    a = min(abs(pct), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)

def chunk(text: str, limit: int = 3500):
    parts, buf = [], ""
    for line in text.splitlines(True):
        if len(buf) + len(line) > limit:
            parts.append(buf)
            buf = ""
        buf += line
    if buf.strip():
        parts.append(buf)
    return parts


# =========================
# TELEGRAM
# =========================
def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram není nastaven: TELEGRAMTOKEN/CHATID chybí.")
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
    for p in chunk(text):
        telegram_send(p)


# =========================
# EMAIL (Gmail SMTP) – max 1× denně
# =========================
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


# =========================
# FMP – helper
# =========================
def fmp_get(path: str, params: dict):
    if not FMP_API_KEY:
        return None
    url = f"https://financialmodelingprep.com/api/{path}"
    params = dict(params or {})
    params["apikey"] = FMP_API_KEY
    try:
        r = requests.get(url, params=params, timeout=25)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None


# =========================
# COMPANY PROFILE: FMP primary, fallback yfinance
# =========================
def load_profiles_cache():
    return read_json(PROFILE_CACHE_FILE, {})

def save_profiles_cache(cache):
    write_json(PROFILE_CACHE_FILE, cache)

def profile_get(ticker: str):
    cache = load_profiles_cache()
    if ticker in cache:
        return cache[ticker]

    prof = None

    # FMP primary
    data = fmp_get("v3/profile", {"symbol": ticker})
    if isinstance(data, list) and data:
        row = data[0]
        prof = {
            "name": (row.get("companyName") or "").strip(),
            "sector": (row.get("sector") or "").strip(),
            "industry": (row.get("industry") or "").strip(),
            "description": (row.get("description") or "").strip()
        }

    # Fallback: yfinance info (není vždy spolehlivé)
    if not prof or not prof.get("name"):
        try:
            info = yf.Ticker(ticker).info or {}
            prof = prof or {}
            prof["name"] = prof.get("name") or (info.get("longName") or info.get("shortName") or "").strip()
            prof["sector"] = prof.get("sector") or (info.get("sector") or "").strip()
            prof["industry"] = prof.get("industry") or (info.get("industry") or "").strip()
            prof["description"] = prof.get("description") or (info.get("longBusinessSummary") or "").strip()
        except:
            pass

    if not prof:
        prof = {"name": ticker, "sector": "", "industry": "", "description": ""}

    cache[ticker] = prof
    save_profiles_cache(cache)
    return prof


# =========================
# PRICES: FMP primary (daily), Yahoo fallback (daily + intraday)
# =========================
def prices_daily_fmp(ticker: str):
    """
    Vrací (last_close, prev_close).
    """
    data = fmp_get("v3/historical-price-full/" + ticker, {"serietype": "line", "timeseries": 5})
    if not data or not isinstance(data, dict):
        return None
    hist = data.get("historical")
    if not isinstance(hist, list) or len(hist) < 2:
        return None
    # historické jsou obvykle seřazené od nejnovějšího
    c0 = safe_float(hist[0].get("close"))
    c1 = safe_float(hist[1].get("close"))
    if c0 is None or c1 is None:
        return None
    return c0, c1

def prices_daily_yahoo(ticker: str):
    """
    Vrací (last_close, prev_close).
    """
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

def daily_last_prev_close(ticker: str):
    # FMP primary
    got = prices_daily_fmp(ticker)
    if got:
        return got[0], got[1], "FMP"
    # fallback Yahoo
    got = prices_daily_yahoo(ticker)
    if got:
        return got[0], got[1], "Yahoo"
    return None, None, "—"

def intraday_open_last_yahoo(ticker: str):
    """
    Intraday pro alerty: (open, last) z yfinance 5m.
    """
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
    """
    Volume spike = poslední denní volume / průměr 20 dnů (yfinance).
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
    except:
        return 1.0


# =========================
# NEWS: FMP + RSS (Yahoo + SeekingAlpha + Google)
# =========================
def rss_entries(url: str, limit: int):
    feed = feedparser.parse(url)
    out = []
    for e in (feed.entries or [])[:limit]:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        if title:
            out.append((title, link))
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
    (["earnings", "results", "quarter", "q1", "q2", "q3", "q4", "beat", "miss"], "výsledky (earnings) / překvapení vs očekávání"),
    (["guidance", "outlook", "forecast", "raises", "cuts"], "výhled (guidance) / změna očekávání"),
    (["upgrade", "downgrade", "price target", "rating"], "analytické doporučení (upgrade/downgrade/target)"),
    (["acquire", "acquisition", "merger", "deal"], "M&A / akvizice / transakce"),
    (["sec", "investigation", "lawsuit", "regulator", "antitrust"], "regulace / vyšetřování / právní zprávy"),
    (["contract", "partnership", "orders"], "zakázky / partnerství / objednávky"),
    (["chip", "ai", "gpu", "data center", "datacenter", "semiconductor"], "AI/čipy – sektorové zprávy"),
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


# =========================
# EARNINGS: FMP calendar (primary)
# =========================
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


# =========================
# SCORE (praktické)
# =========================
W_MOVE = 1.0
W_VOL = 0.7
W_NEWS = 0.4
W_EARN = 0.6

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

def compute_score(move_abs, vol_spike, news_count, earn_days):
    return (
        W_MOVE * clamp(move_abs, 0, 10) +
        W_VOL  * clamp(vol_spike, 0, 5) +
        W_NEWS * clamp(float(news_count), 0, 6) +
        W_EARN * clamp(earnings_score(earn_days), 0, 3)
    )

def score_explain(move_abs, vol_spike, news_count, earn_days):
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

    if earn_days is not None:
        if earn_days <= 2:
            parts.append("earnings velmi blízko")
        elif earn_days <= 7:
            parts.append("earnings do týdne")
        elif earn_days <= 14:
            parts.append("earnings do 2 týdnů")

    return ", ".join(parts) + "."


# =========================
# GRAF do emailu (denní změna)
# =========================
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


# =========================
# JOB 12:00 – report + email 1× denně
# =========================
def premarket_job():
    now = now_local()
    if hm(now) != PREMARKET_TIME:
        return
    if read_text(LAST_PREMARKET_DATE_FILE, "") == today_str():
        return

    rows = []
    earnings_today, earnings_tom = [], []
    today_d = date.today()
    tom_d = today_d + timedelta(days=1)

    for t in PORTFOLIO:
        last, prev, src = daily_last_prev_close(t)
        if last is None:
            continue
        ch = pct_change(last, prev)

        ed = fmp_next_earnings_date(t)
        if ed == today_d:
            earnings_today.append(t)
        elif ed == tom_d:
            earnings_tom.append(t)

        prof = profile_get(t)
        rows.append((t, prof, last, ch, src))

    rows.sort(key=lambda x: abs(x[3]) if x[3] is not None else -1, reverse=True)

    msg = []
    msg.append(f"🕛 REPORT 12:00 ({now.strftime('%d.%m.%Y %H:%M')})")
    msg.append("⚠️ Informativní přehled (ne investiční doporučení).")
    msg.append("")
    if earnings_today:
        msg.append("📣 Earnings DNES: " + ", ".join(earnings_today))
    if earnings_tom:
        msg.append("⏰ Earnings ZÍTRA: " + ", ".join(earnings_tom))
    msg.append("")

    msg.append("📌 TOP pohyby (close vs předchozí close):")
    for t, prof, last, ch, src in rows[:12]:
        nm = prof.get("name") or t
        sec = (prof.get("sector") or "").strip()
        sec_txt = f" [{sec}]" if sec else ""
        if ch is None:
            msg.append(f"• {t} — {nm}{sec_txt}: {last:.2f} (n/a)  ({src})")
        else:
            msg.append(f"• {t} — {nm}{sec_txt}: {last:.2f} ({ch:+.2f}%) {bar(ch)}  ({src})")

        news = combined_news(t, 1)
        if news:
            srcN, titleN, _ = news[0]
            msg.append(f"   📰 {srcN}: {titleN}")

    telegram_send_long("\n".join(msg))
    write_text(LAST_PREMARKET_DATE_FILE, today_str())

    # Email max 1× denně (jen v 12:00 reportu)
    if EMAIL_ENABLED and read_text(LAST_EMAIL_DATE_FILE, "") != today_str():
        changes = {}
        for t, prof, last, ch, src in rows:
            if ch is not None:
                changes[t] = ch

        chart_path = os.path.join(STATE_DIR, f"daily_change_{today_str()}.png")
        try:
            make_change_chart(dict(list(changes.items())[:16]), chart_path)
            images = [chart_path]
        except Exception as e:
            print("Chart error:", e)
            images = []

        body = []
        body.append(f"REPORT 12:00 ({now.strftime('%d.%m.%Y %H:%M')} – {TZ_NAME})")
        body.append("Zdroj cen: FMP primárně, fallback Yahoo/yfinance.")
        body.append("")
        if earnings_today:
            body.append("Earnings DNES: " + ", ".join(earnings_today))
        if earnings_tom:
            body.append("Earnings ZÍTRA: " + ", ".join(earnings_tom))
        body.append("")
        body.append("Top pohyby:")
        for t, prof, last, ch, src in rows[:15]:
            nm = prof.get("name") or t
            sec = (prof.get("sector") or "").strip()
            sec_txt = f" [{sec}]" if sec else ""
            if ch is None:
                body.append(f"- {t} — {nm}{sec_txt} | {last:.2f} | n/a | {src}")
            else:
                body.append(f"- {t} — {nm}{sec_txt} | {last:.2f} | {ch:+.2f}% | {src}")

        body.append("")
        body.append("Rychlé novinky (mix FMP + Yahoo RSS + SeekingAlpha RSS + Google News):")
        for t, prof, last, ch, src in rows[:8]:
            news = combined_news(t, NEWS_PER_TICKER)
            if not news:
                continue
            nm = prof.get("name") or t
            body.append(f"\n{t} — {nm}")
            for sN, titleN, linkN in news[:NEWS_PER_TICKER]:
                if linkN:
                    body.append(f"  • ({sN}) {titleN} — {linkN}")
                else:
                    body.append(f"  • ({sN}) {titleN}")

        email_send(
            subject=f"📧 Report 12:00 – {now.strftime('%d.%m.%Y')}",
            body_text="\n".join(body),
            image_paths=images
        )
        write_text(LAST_EMAIL_DATE_FILE, today_str())


# =========================
# ALERTY 12–21 každých 15 min (od dnešního OPEN) – Yahoo intraday
# =========================
def should_send_alert(ticker: str, change_open: float) -> bool:
    last = read_json(LAST_ALERTS_FILE, {})
    last_val = last.get(ticker)
    if last_val is None:
        return True
    # anti-spam: další alert až když se to pohne o 1% oproti poslednímu alertu
    return abs(change_open - last_val) >= 1.0

def mark_alert(ticker: str, change_open: float):
    last = read_json(LAST_ALERTS_FILE, {})
    last[ticker] = change_open
    write_json(LAST_ALERTS_FILE, last)

def alerts_job():
    now = now_local()
    now_hm = hm(now)
    if not in_window(now_hm, ALERT_START, ALERT_END):
        return

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

        prof = profile_get(t)
        name = prof.get("name") or t
        sector = (prof.get("sector") or "").strip()
        sec_txt = f" [{sector}]" if sector else ""
        sign = "🟩" if ch >= 0 else "🟥"
        arrow = "📈" if ch >= 0 else "📉"

        news = combined_news(t, 2)
        why = why_from_headlines(news)

        msg = []
        msg.append(f"🚨 ALERT {sign} {t}")
        msg.append(f"{name}{sec_txt}")
        msg.append(f"Změna od dnešního OPEN: {ch:+.2f}% {arrow} {bar(ch)}")
        msg.append(f"Aktuální cena: {last:.2f}")
        msg.append(f"Důvod (z headlines): {why}")
        msg.append(f"Čas: {now_hm}")

        telegram_send("\n".join(msg))
        mark_alert(t, ch)


# =========================
# 20:00 – večerní shrnutí + TOP tipy (max 5)
# =========================
def opportunities_scored():
    rows = []
    for t in OPPORTUNITY_WATCHLIST:
        last, prev, src = daily_last_prev_close(t)
        if last is None:
            continue
        ch = pct_change(last, prev)
        move_abs = abs(ch) if ch is not None else 0.0

        vol_spike = volume_spike_yahoo(t)
        news_items = combined_news(t, NEWS_PER_TICKER)
        news_count = len(news_items)

        edays = days_to_earnings(t)
        score = compute_score(move_abs, vol_spike, news_count, edays)

        prof = profile_get(t)

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
            "src": src
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:OPPORTUNITY_MAX]

def evening_job():
    now = now_local()
    if hm(now) != EVENING_TIME:
        return
    if read_text(LAST_EVENING_DATE_FILE, "") == today_str():
        return
    if OPPORTUNITY_WEEKDAYS_ONLY and not is_weekday(now):
        return

    # Shrnutí portfolia
    rows = []
    for t in PORTFOLIO:
        last, prev, src = daily_last_prev_close(t)
        if last is None:
            continue
        ch = pct_change(last, prev)
        prof = profile_get(t)
        rows.append((t, prof, last, ch, src))

    rows.sort(key=lambda x: abs(x[3]) if x[3] is not None else -1, reverse=True)

    msg = []
    msg.append(f"🕗 VEČERNÍ SHRNUTÍ ({now.strftime('%d.%m.%Y %H:%M')})")
    msg.append("⚠️ Informativní přehled (ne investiční doporučení).")
    msg.append("")
    msg.append("📌 TOP pohyby (close vs předchozí close):")
    for t, prof, last, ch, src in rows[:10]:
        nm = prof.get("name") or t
        sec = (prof.get("sector") or "").strip()
        sec_txt = f" [{sec}]" if sec else ""
        if ch is None:
            msg.append(f"• {t} — {nm}{sec_txt}: {last:.2f} (n/a)  ({src})")
        else:
            msg.append(f"• {t} — {nm}{sec_txt}: {last:.2f} ({ch:+.2f}%) {bar(ch)}  ({src})")

    # Tipy
    tips = opportunities_scored()
    msg.append("")
    msg.append(f"💡 TOP {OPPORTUNITY_MAX} příležitosti (AI/čipy/kovy) – scoring")
    msg.append("Score = pohyb + volume spike + počet zpráv + blízkost earnings.")
    msg.append("")

    for r in tips:
        t = r["ticker"]
        nm = r["name"]
        sec = r["sector"]
        ind = r["industry"]
        ch = r["ch"]
        last = r["last"]
        score = r["score"]
        arrow = "📈" if (ch is not None and ch >= 0) else "📉"
        sec_txt = f" [{sec}]" if sec else ""

        header = f"{arrow} {t} — {nm}{sec_txt} | {last:.2f}"
        if ch is not None:
            header += f" ({ch:+.2f}%) {bar(ch)}"
        header += f" | SCORE {score:.2f} | zdroj cen: {r['src']}"

        msg.append(header)
        msg.append(f"• Proč v TOP: {score_explain(abs(ch) if ch else 0.0, r['vol_spike'], len(r['news_items']), r['earn_days'])}")
        note = earnings_note(r["earn_days"])
        if note:
            msg.append(f"• Riziko: {note}")
        msg.append(f"• Proč se to hýbe (z headlines): {r['why']}")

        # „co dělá firma“ z FMP profilu – zkrátíme na 1–2 věty
        desc = (r["desc"] or "").strip()
        if desc:
            short = desc[:280].rstrip()
            msg.append(f"• Co firma dělá: {short}…")

        if r["news_items"]:
            srcN, titleN, linkN = r["news_items"][0]
            msg.append(f"• Top zpráva: [{srcN}] {titleN}")

        msg.append("")

    telegram_send_long("\n".join(msg))
    write_text(LAST_EVENING_DATE_FILE, today_str())


# =========================
# MAIN (běží 1× při každém GitHub runu)
# =========================
def main():
    # 12:00 report (+ email max 1× denně)
    premarket_job()

    # alerty 12–21 (každý run = každých 15 min podle cron)
    alerts_job()

    # 20:00 evening
    evening_job()

    print("✅ Hotovo:", now_local().strftime("%d.%m.%Y %H:%M"))

if __name__ == "__main__":
    main()
