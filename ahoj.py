import os
import json
import math
import pytz
import time
import requests
import feedparser
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, date, timedelta

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


# =========================
# ENV (GitHub Secrets)
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAMTOKEN", "").strip()
CHAT_ID = str(os.getenv("CHATID", "")).strip()

FMP_API_KEY = os.getenv("FMPAPIKEY", "").strip()
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()  # volitelné

EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAILPASSWORD", "").strip()

TIMEZONE = os.getenv("TIMEZONE", "Europe/Prague").strip()
tz = pytz.timezone(TIMEZONE)

# Časy
PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()   # Praha – premarket briefing (Telegram)
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()       # Praha – příležitosti (Telegram) + 1× denně email digest
ALERT_START = os.getenv("ALERT_START", "15:30").strip()         # Praha
ALERT_END = os.getenv("ALERT_END", "21:00").strip()             # Praha

# Alert prahy
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3"))       # % od dnešního OPEN

# News
NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2"))         # z každého zdroje (Yahoo/SA/Google)
# (překlady jsme vypnuli kvůli stabilitě; když budeš chtít, doplním bezpečně zpět)

# Portfolio
PORTFOLIO_ENV = os.getenv("PORTFOLIO", "").strip()
DEFAULT_PORTFOLIO = [
    "CENX","S","NVO","PYPL","AMZN","MSFT","CVX","NVDA","TSM","CAG","META","AAPL","GOOGL","TSLA",
    "PLTR","SPY","FCX","IREN"
]
PORTFOLIO = [t.strip().upper() for t in PORTFOLIO_ENV.split(",") if t.strip()] if PORTFOLIO_ENV else DEFAULT_PORTFOLIO

# Watchlist příležitostí (AI / čipy / kovy) – stabilní základ
OPPORTUNITY_MAX = int(os.getenv("OPPORTUNITY_MAX", "5"))
OPPORTUNITY_WATCHLIST = [
    # AI / čipy
    "NVDA","TSM","ASML","AMD","AVGO","MU","ARM","INTC","QCOM","SMCI",
    # hyperscalers / AI infra
    "AMZN","MSFT","GOOGL",
    # kovy a těžba pro elektrifikaci/AI
    "FCX","RIO","BHP","SCCO","AA","CENX","TECK"
]


# =========================
# STATE (persist přes cache)
# =========================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)
STATE_FILE = os.path.join(STATE_DIR, "state.json")
SEC_MAP_FILE = os.path.join(STATE_DIR, "sec_ticker_to_cik.json")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

STATE = load_json(STATE_FILE, {})
STATE.setdefault("premarket_sent_date", None)     # YYYY-MM-DD
STATE.setdefault("evening_sent_date", None)       # YYYY-MM-DD (Telegram příležitosti)
STATE.setdefault("email_sent_date", None)         # YYYY-MM-DD (Email digest 1×)
STATE.setdefault("alerts_sent", {})               # {date: { "TICKER:UP/DOWN": true }}


# =========================
# Helpers
# =========================
def now_local():
    return datetime.now(tz)

def hm_to_minutes(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)

def after_time(dt: datetime, target_hm: str) -> bool:
    return (dt.hour * 60 + dt.minute) >= hm_to_minutes(target_hm)

def in_window(dt: datetime, start_hm: str, end_hm: str) -> bool:
    cur = dt.hour * 60 + dt.minute
    return hm_to_minutes(start_hm) <= cur <= hm_to_minutes(end_hm)

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


# =========================
# Telegram
# =========================
def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Chybí TELEGRAMTOKEN nebo CHATID (Secrets).")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    r = requests.post(url, data=payload, timeout=35)
    print("Telegram status:", r.status_code)
    if r.status_code != 200:
        print("Telegram odpověď:", r.text[:500])
        return False
    return True


# =========================
# Email (HTML + inline obrázky)
# =========================
def send_email_html(subject: str, html_body: str, inline_images: dict) -> bool:
    if not EMAIL_ENABLED:
        return False
    if not (EMAIL_SENDER and EMAIL_RECEIVER and GMAIL_APP_PASSWORD):
        print("⚠️ Email zapnutý, ale chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")
        return False

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("Report je v HTML formátu.", "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    for cid, path in inline_images.items():
        try:
            with open(path, "rb") as f:
                img = MIMEImage(f.read())
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
            msg.attach(img)
        except Exception as e:
            print("⚠️ Nelze připojit obrázek:", path, e)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=40) as server:
            server.login(EMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_SENDER, [EMAIL_RECEIVER], msg.as_string())
        print("✅ Email odeslán.")
        return True
    except Exception as e:
        print("⚠️ Email error:", e)
        return False


# =========================
# Data sources: Prices (Yahoo → FMP → Stooq)
# =========================
def yahoo_daily_last_two_closes(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="10d", interval="1d")
        if h is None or h.empty:
            return None
        closes = h["Close"].dropna()
        if len(closes) < 2:
            return None
        return safe_float(closes.iloc[-1]), safe_float(closes.iloc[-2])
    except:
        return None

def yahoo_today_open_close(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="5d", interval="1d")
        if h is None or h.empty:
            return None
        row = h.iloc[-1]
        o = safe_float(row.get("Open"))
        c = safe_float(row.get("Close"))
        return o, c
    except:
        return None

def fmp_quote_price(ticker: str):
    if not FMP_API_KEY:
        return None
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={FMP_API_KEY}"
        r = requests.get(url, timeout=25)
        if r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, list) or not data:
            return None
        return safe_float(data[0].get("price"))
    except:
        return None

def stooq_last_close_us(ticker: str):
    """
    Stooq free daily CSV, většinou pro US tickery s příponou .US
    Např. AAPL.US
    """
    try:
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
        r = requests.get(url, timeout=25)
        if r.status_code != 200 or "Date,Open,High,Low,Close,Volume" not in r.text:
            return None
        lines = [ln.strip() for ln in r.text.splitlines() if ln.strip()]
        if len(lines) < 3:
            return None
        last = lines[-1].split(",")
        close = safe_float(last[4]) if len(last) >= 5 else None
        return close
    except:
        return None

def get_last_close_best_effort(ticker: str):
    # 1) Yahoo
    closes = yahoo_daily_last_two_closes(ticker)
    if closes:
        return closes[0]
    # 2) FMP quote (aktuální)
    p = fmp_quote_price(ticker)
    if p is not None:
        return p
    # 3) Stooq
    return stooq_last_close_us(ticker)

def get_yday_change_best_effort(ticker: str):
    """
    (last_close, prev_close, pct) – primárně Yahoo (nejčistší pro 2 closy).
    """
    closes = yahoo_daily_last_two_closes(ticker)
    if closes:
        last, prev = closes
        if last is not None and prev is not None:
            return last, prev, pct_change(last, prev)
    # fallback: když neumíme 2 dny, vrátíme aspoň poslední cenu
    last = get_last_close_best_effort(ticker)
    return last, None, None


# =========================
# News sources: Yahoo RSS + SeekingAlpha RSS + Google News RSS + PRNewswire/BusinessWire + SEC filings
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

def news_yahoo(ticker: str, limit: int):
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    return [("Yahoo", t, l) for t, l in rss_entries(url, limit)]

def news_seekingalpha(ticker: str, limit: int):
    url = f"https://seekingalpha.com/symbol/{ticker}.xml"
    return [("SeekingAlpha", t, l) for t, l in rss_entries(url, limit)]

def news_google(ticker: str, limit: int):
    # Google News RSS search
    q = requests.utils.quote(f"{ticker} stock OR {ticker} earnings OR {ticker} guidance")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return [("GoogleNews", t, l) for t, l in rss_entries(url, limit)]

def news_pr_businesswire_filtered(ticker: str, limit_total: int):
    """
    Bereme obecné PR RSS a filtrujeme podle toho, zda ticker/klíč je v titulku.
    """
    sources = [
        ("PRNewswire", "https://www.prnewswire.com/rss/news-releases-list.rss"),
        ("BusinessWire", "https://www.businesswire.com/portal/site/home/rss/"),
    ]
    out = []
    key = ticker.upper()
    for src, url in sources:
        try:
            items = rss_entries(url, 30)
            for title, link in items:
                if key in title.upper():
                    out.append((src, title, link))
                if len(out) >= limit_total:
                    return out
        except:
            continue
    return out

def sec_user_agent_headers():
    # SEC vyžaduje User-Agent s kontaktem (stačí obecný popis)
    return {
        "User-Agent": "XTB-InvestBot/1.0 (contact: berq1994@gmail.com)"
    }

def load_sec_ticker_map():
    m = load_json(SEC_MAP_FILE, {})
    if m:
        return m
    # stáhneme oficiální mapu ticker->CIK
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        r = requests.get(url, headers=sec_user_agent_headers(), timeout=35)
        if r.status_code != 200:
            return {}
        data = r.json()
        # data je dict index-> {cik_str, ticker, title}
        out = {}
        for _, row in data.items():
            t = (row.get("ticker") or "").upper().strip()
            cik = row.get("cik_str")
            if t and cik:
                out[t] = str(cik).zfill(10)  # CIK 10 digits
        save_json(SEC_MAP_FILE, out)
        return out
    except:
        return {}

SEC_TICKER_TO_CIK = load_sec_ticker_map()

def news_sec_filings(ticker: str, limit: int):
    """
    SEC Atom feed: poslední filingy (8-K/10-Q/10-K mix)
    """
    cik = SEC_TICKER_TO_CIK.get(ticker.upper())
    if not cik:
        return []
    try:
        # Atom feed pro firmu (latest filings)
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&count=10&output=atom"
        r = requests.get(url, headers=sec_user_agent_headers(), timeout=35)
        if r.status_code != 200:
            return []
        feed = feedparser.parse(r.text)
        out = []
        for e in (feed.entries or [])[:limit]:
            title = (getattr(e, "title", "") or "").strip()
            link = (getattr(e, "link", "") or "").strip()
            if title:
                out.append(("SEC", title, link))
        return out
    except:
        return []

def combined_news(ticker: str, limit_each: int):
    news = []
    news += news_yahoo(ticker, limit_each)
    news += news_seekingalpha(ticker, limit_each)
    news += news_google(ticker, limit_each)
    news += news_pr_businesswire_filtered(ticker, max(2, limit_each))
    news += news_sec_filings(ticker, max(2, limit_each))
    # odstraníme duplicity podle (title)
    seen = set()
    uniq = []
    for src, title, link in news:
        key = title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((src, title, link))
    return uniq


# =========================
# Earnings: FMP + volitelně Finnhub
# =========================
def fmp_next_earnings_date(ticker: str):
    if not FMP_API_KEY:
        return None
    try:
        url = f"https://financialmodelingprep.com/api/v3/earning_calendar?symbol={ticker}&apikey={FMP_API_KEY}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
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
    except:
        return None

def finnhub_next_earnings_date(ticker: str):
    if not FINNHUB_API_KEY:
        return None
    try:
        # Finnhub earnings calendar (approx): /calendar/earnings?symbol=...
        url = f"https://finnhub.io/api/v1/calendar/earnings?symbol={ticker}&token={FINNHUB_API_KEY}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        cal = data.get("earningsCalendar", [])
        if not cal:
            return None
        today = date.today()
        future = []
        for row in cal:
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
    except:
        return None

def next_earnings_best(ticker: str):
    # nejdřív FMP, pak Finnhub jako backup
    d = fmp_next_earnings_date(ticker)
    if d:
        return d
    return finnhub_next_earnings_date(ticker)


# =========================
# Charts
# =========================
def make_chart(ticker: str, out_path: str, days: int = 7):
    try:
        h = yf.Ticker(ticker).history(period="30d", interval="1d")
        if h is None or h.empty:
            return None
        closes = h["Close"].dropna()
        if len(closes) < 3:
            return None
        closes = closes.iloc[-days:]
        plt.figure(figsize=(6.4, 2.4))
        plt.plot(closes.index, closes.values)
        plt.title(f"{ticker} — poslední dny")
        plt.xticks(rotation=0, fontsize=8)
        plt.tight_layout()
        plt.savefig(out_path, dpi=140)
        plt.close()
        return out_path
    except:
        return None


# =========================
# JOBS
# =========================
def premarket_job():
    """
    12:00 Praha – rychlý Telegram briefing:
    - earnings dnes/zítra
    - top změny včera (close vs close)
    """
    ts = now_local()
    today_str = ts.strftime("%Y-%m-%d")

    if STATE.get("premarket_sent_date") == today_str:
        return
    if not after_time(ts, PREMARKET_TIME):
        return

    today = date.today()
    tomorrow = today + timedelta(days=1)

    e_today, e_tom = [], []
    rows = []

    for t in PORTFOLIO:
        last, prev, pct = get_yday_change_best_effort(t)
        if last is None:
            continue
        ed = next_earnings_best(t)
        if ed == today:
            e_today.append(t)
        elif ed == tomorrow:
            e_tom.append(t)
        rows.append((t, pct, last))

    rows.sort(key=lambda x: abs(x[1]) if x[1] is not None else -1, reverse=True)

    lines = []
    lines.append(f"🕛 Premarket briefing ({ts.strftime('%d.%m.%Y %H:%M')})")
    if e_today:
        lines.append("📣 Earnings DNES: " + ", ".join(e_today))
    if e_tom:
        lines.append("⏰ Earnings ZÍTRA: " + ", ".join(e_tom))
    lines.append("")
    lines.append("Top pohyby (včerejší close vs předchozí close):")
    for (t, pct, last) in rows[:10]:
        if pct is None:
            lines.append(f"• {t}: {last:.2f} (změna n/a)")
        else:
            sign = "+" if pct >= 0 else ""
            lines.append(f"• {t}: {last:.2f} ({sign}{pct:.2f}%)")

    send_telegram("\n".join(lines))

    STATE["premarket_sent_date"] = today_str
    save_json(STATE_FILE, STATE)


def session_alerts_job():
    """
    15:30–21:00 Praha – alerty ±3 % od dnešního OPEN na Telegram.
    (Best effort: open/close z daily. Intraday realtime bez placeného feedu není 100%.)
    """
    ts = now_local()
    if not in_window(ts, ALERT_START, ALERT_END):
        return

    today_str = ts.strftime("%Y-%m-%d")
    sent_today = STATE["alerts_sent"].get(today_str, {})

    for t in PORTFOLIO:
        oc = yahoo_today_open_close(t)
        if not oc:
            continue
        o, c = oc
        if o is None or c is None or o == 0:
            continue

        pct = pct_change(c, o)
        if pct is None:
            continue
        if abs(pct) < ALERT_THRESHOLD:
            continue

        sign = "UP" if pct > 0 else "DOWN"
        key = f"{t}:{sign}"
        if sent_today.get(key):
            continue

        arrow = "📈" if pct > 0 else "📉"
        send_telegram(
            f"🚨 ALERT {arrow}\n"
            f"{t}: {pct:+.2f}% od dnešního OPEN\n"
            f"Okno: {ALERT_START}–{ALERT_END} | Čas: {ts.strftime('%H:%M')}"
        )
        sent_today[key] = True

    STATE["alerts_sent"][today_str] = sent_today
    save_json(STATE_FILE, STATE)


def build_opportunities():
    """
    TOP příležitosti: vybere z watchlistu AI/čipy/kovy
    podle největší absolutní změny za včerejšek + přidá top headlines.
    """
    rows = []
    for t in OPPORTUNITY_WATCHLIST:
        last, prev, pct = get_yday_change_best_effort(t)
        if last is None:
            continue
        score = abs(pct) if pct is not None else 0
        rows.append((t, last, pct, score))
    rows.sort(key=lambda x: x[3], reverse=True)
    return rows[:OPPORTUNITY_MAX]


def evening_job():
    """
    20:00 Praha – Telegram: příležitosti + mini-news
    20:00 Praha – Email: JEDNOU denně velký digest (portfolio + grafy + news + earnings + opportunities)
    """
    ts = now_local()
    today_str = ts.strftime("%Y-%m-%d")

    if not after_time(ts, EVENING_TIME):
        return

    # 20:00 Telegram opportunities 1× denně
    if STATE.get("evening_sent_date") != today_str:
        opp = build_opportunities()
        lines = []
        lines.append(f"🕗 Večerní přehled příležitostí ({ts.strftime('%d.%m.%Y %H:%M')})")
        lines.append(f"Téma: AI / čipy / kovy | výběr: TOP {OPPORTUNITY_MAX}")
        lines.append("")
        for (t, last, pct, _) in opp:
            if pct is None:
                lines.append(f"• {t}: {last:.2f} (změna n/a)")
            else:
                sign = "+" if pct >= 0 else ""
                lines.append(f"• {t}: {last:.2f} ({sign}{pct:.2f}%)")
            news = combined_news(t, 1)
            if news:
                src, title, link = news[0]
                lines.append(f"  - {src}: {title}")
        send_telegram("\n".join(lines))

        STATE["evening_sent_date"] = today_str
        save_json(STATE_FILE, STATE)

    # 20:00 Email digest 1× denně
    if EMAIL_ENABLED and STATE.get("email_sent_date") != today_str:
        send_daily_email_digest(ts)
        STATE["email_sent_date"] = today_str
        save_json(STATE_FILE, STATE)


def send_daily_email_digest(ts: datetime):
    def col(p):
        return "#1f8b4c" if (p is not None and p >= 0) else "#c0392b"

    # Portfolio řádky
    portfolio_rows = []
    for t in PORTFOLIO:
        last, prev, pct = get_yday_change_best_effort(t)
        if last is None:
            continue
        portfolio_rows.append((t, last, prev, pct))
    portfolio_rows.sort(key=lambda x: abs(x[3]) if x[3] is not None else -1, reverse=True)

    # Earnings today/tomorrow
    today = date.today()
    tomorrow = today + timedelta(days=1)
    e_today, e_tom = [], []
    for t in PORTFOLIO:
        ed = next_earnings_best(t)
        if ed == today:
            e_today.append(t)
        elif ed == tomorrow:
            e_tom.append(t)

    # Opportunities
    opp = build_opportunities()

    # Inline grafy – ať email není obří (top 12)
    inline = {}
    for (t, _, _, _) in portfolio_rows[:12]:
        path = os.path.join(STATE_DIR, f"chart_{t}.png")
        p = make_chart(t, path, days=7)
        if p:
            inline[f"chart_{t}"] = p

    # HTML
    html = []
    html.append(f"<h2>Denní report — {ts.strftime('%d.%m.%Y %H:%M')} ({TIMEZONE})</h2>")
    html.append("<p><b>Data:</b> Yahoo (yfinance) + FMP + Stooq fallback | News: Yahoo RSS, SeekingAlpha RSS, GoogleNews RSS, PR filtry, SEC filings.</p>")

    if e_today or e_tom:
        html.append("<h3>Earnings</h3>")
        if e_today:
            html.append("<p><b>Dnes:</b> " + ", ".join(e_today) + "</p>")
        if e_tom:
            html.append("<p><b>Zítra:</b> " + ", ".join(e_tom) + "</p>")

    html.append("<h3>Portfolio — změna za poslední obchodní den</h3>")
    html.append("""
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px;">
<tr style="background:#f2f2f2;">
  <th>Ticker</th><th>Close</th><th>Předchozí</th><th>Změna</th><th>Graf</th><th>Top zpráva</th>
</tr>
""")

    for (t, last, prev, pct) in portfolio_rows:
        if pct is None:
            change_str = "n/a"
            color = "#555"
            sign = ""
        else:
            sign = "+" if pct >= 0 else ""
            change_str = f"{sign}{pct:.2f}%"
            color = col(pct)

        cid = f"chart_{t}"
        img_html = f'<img src="cid:{cid}" width="320" style="display:block;">' if cid in inline else "—"

        news = combined_news(t, 1)
        if news:
            src, title, link = news[0]
            news_html = f'[{src}] <a href="{link}">{title}</a>' if link else f'[{src}] {title}'
        else:
            news_html = "—"

        prev_str = f"{prev:.2f}" if prev is not None else "—"
        html.append(f"""
<tr>
  <td><b>{t}</b></td>
  <td>{last:.2f}</td>
  <td>{prev_str}</td>
  <td style="color:{color};"><b>{change_str}</b></td>
  <td>{img_html}</td>
  <td>{news_html}</td>
</tr>
""")

    html.append("</table>")

    html.append(f"<h3>Příležitosti (AI / čipy / kovy) — TOP {OPPORTUNITY_MAX}</h3><ul>")
    for (t, last, pct, _) in opp:
        if pct is None:
            html.append(f"<li><b>{t}</b>: {last:.2f} (změna n/a)</li>")
        else:
            sign = "+" if pct >= 0 else ""
            html.append(f"<li><b>{t}</b>: {last:.2f} (<span style='color:{col(pct)}'><b>{sign}{pct:.2f}%</b></span>)</li>")
            n = combined_news(t, 1)
            if n:
                src, title, link = n[0]
                if link:
                    html.append(f"<ul><li>{src}: <a href='{link}'>{title}</a></li></ul>")

    html.append("</ul>")
    html.append("<p style='color:#666'>Pozn.: Seeking Alpha může mít část obsahu za paywallem – posílám jen titulky a odkazy.</p>")

    subject = f"Denní report {ts.strftime('%Y-%m-%d')} — portfolio + earnings + news + příležitosti"
    send_email_html(subject, "\n".join(html), inline)


def main():
    # 1) premarket 12:00 (Telegram)
    premarket_job()
    # 2) alerts 15:30–21:00 (Telegram, ±3 %)
    session_alerts_job()
    # 3) evening 20:00 (Telegram opportunities + Email digest 1× denně)
    evening_job()

if __name__ == "__main__":
    main()
