import os
import json
import math
import pytz
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

EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAILPASSWORD", "").strip()

TIMEZONE = os.getenv("TIMEZONE", "Europe/Prague").strip()
tz = pytz.timezone(TIMEZONE)

# Časy (Praha)
PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()
ALERT_START = os.getenv("ALERT_START", "12:00").strip()
ALERT_END = os.getenv("ALERT_END", "21:00").strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3"))  # %

NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2"))
OPPORTUNITY_MAX = int(os.getenv("OPPORTUNITY_MAX", "5"))

PORTFOLIO_ENV = os.getenv("PORTFOLIO", "").strip()
DEFAULT_PORTFOLIO = [
    "CENX","S","NVO","PYPL","AMZN","MSFT","CVX","NVDA","TSM","CAG","META","AAPL","GOOGL","TSLA",
    "PLTR","SPY","FCX","IREN"
]
PORTFOLIO = [t.strip().upper() for t in PORTFOLIO_ENV.split(",") if t.strip()] if PORTFOLIO_ENV else DEFAULT_PORTFOLIO

# Watchlist příležitostí (AI / čipy / kovy) – můžeš rozšířit kdykoliv
OPPORTUNITY_WATCHLIST = [
    "NVDA","TSM","ASML","AMD","AVGO","MU","ARM","INTC","QCOM","SMCI",
    "AMZN","MSFT","GOOGL",
    "FCX","RIO","BHP","SCCO","AA","CENX","TECK"
]


# =========================
# Názvy firem (lepší čitelnost v reportu)
# =========================
COMPANY_NAMES = {
    "CENX": "Century Aluminum",
    "S": "SentinelOne",
    "NVO": "Novo Nordisk",
    "PYPL": "PayPal",
    "AMZN": "Amazon",
    "MSFT": "Microsoft",
    "CVX": "Chevron",
    "NVDA": "NVIDIA",
    "TSM": "TSMC",
    "CAG": "Conagra Brands",
    "META": "Meta Platforms",
    "AAPL": "Apple",
    "GOOGL": "Alphabet (Google)",
    "TSLA": "Tesla",
    "PLTR": "Palantir",
    "SPY": "SPDR S&P 500 ETF",
    "FCX": "Freeport-McMoRan",
    "IREN": "Iris Energy",
    "ASML": "ASML",
    "AMD": "AMD",
    "AVGO": "Broadcom",
    "MU": "Micron",
    "ARM": "Arm",
    "INTC": "Intel",
    "QCOM": "Qualcomm",
    "SMCI": "Super Micro Computer",
    "RIO": "Rio Tinto",
    "BHP": "BHP",
    "SCCO": "Southern Copper",
    "AA": "Alcoa",
    "TECK": "Teck Resources",
}


# =========================
# STATE (persist přes cache)
# =========================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)
STATE_FILE = os.path.join(STATE_DIR, "state.json")

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
STATE.setdefault("premarket_sent_date", None)      # YYYY-MM-DD
STATE.setdefault("evening_sent_date", None)        # YYYY-MM-DD
STATE.setdefault("email_sent_date", None)          # YYYY-MM-DD
STATE.setdefault("alerts_sent", {})                # {date: { "TICKER:UP/DOWN": true }}


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

def name_for(ticker: str) -> str:
    return COMPANY_NAMES.get(ticker.upper(), ticker.upper())

def bar(pct: float) -> str:
    """
    Hezčí "grafika" do Telegramu: 10 bloků dle absolutní změny.
    """
    if pct is None:
        return ""
    a = abs(pct)
    # 0–10% mapujeme na 0–10 bloků, víc než 10% = plno
    blocks = min(10, int(round(a)))
    return "█" * blocks + "░" * (10 - blocks)

def chunk_telegram(text: str, limit: int = 3500):
    """
    Telegram má limit ~4096 znaků; necháme rezervu.
    """
    parts = []
    buf = ""
    for line in text.splitlines(True):
        if len(buf) + len(line) > limit:
            parts.append(buf)
            buf = ""
        buf += line
    if buf.strip():
        parts.append(buf)
    return parts


# =========================
# Telegram
# =========================
def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Chybí TELEGRAMTOKEN nebo CHATID (Secrets).")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    r = requests.post(url, data=payload, timeout=35)
    print("Telegram status:", r.status_code)
    if r.status_code != 200:
        print("Telegram odpověď:", r.text[:500])
        return False
    return True

def send_telegram_long(text: str):
    for part in chunk_telegram(text):
        send_telegram(part)


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
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=45) as server:
            server.login(EMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_SENDER, [EMAIL_RECEIVER], msg.as_string())
        print("✅ Email odeslán.")
        return True
    except Exception as e:
        print("⚠️ Email error:", e)
        return False


# =========================
# Prices – PRO: intraday 5m (open vs last) + fallback daily close
# =========================
def intraday_open_last(ticker: str):
    """
    Pokus o intraday data (5m). Vrací (open, last).
    Když trh zavřený / Yahoo nedá intraday, vrátí None.
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

def daily_last_two_closes(ticker: str):
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

def get_yday_change(ticker: str):
    closes = daily_last_two_closes(ticker)
    if not closes:
        return None, None, None
    last, prev = closes
    return last, prev, pct_change(last, prev)


# =========================
# News sources – Yahoo RSS + SeekingAlpha RSS + GoogleNews RSS
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
    q = requests.utils.quote(f"{ticker} stock OR {ticker} earnings OR {ticker} guidance")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return [("GoogleNews", t, l) for t, l in rss_entries(url, limit)]

def combined_news(ticker: str, limit_each: int):
    items = []
    items += news_yahoo(ticker, limit_each)
    items += news_seekingalpha(ticker, limit_each)
    items += news_google(ticker, limit_each)

    # dedup titulky
    seen = set()
    uniq = []
    for src, title, link in items:
        key = title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((src, title, link))
    return uniq


# =========================
# Earnings – FMP (datum)
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


# =========================
# Charts (lepší vizuál: zelená/červená linka)
# =========================
def make_chart_7d(ticker: str, out_path: str):
    try:
        h = yf.Ticker(ticker).history(period="30d", interval="1d")
        if h is None or h.empty:
            return None
        closes = h["Close"].dropna()
        if len(closes) < 5:
            return None
        closes = closes.iloc[-7:]
        delta = closes.iloc[-1] - closes.iloc[0]
        color = "green" if delta >= 0 else "red"

        plt.figure(figsize=(6.4, 2.4))
        plt.plot(closes.index, closes.values, color=color, linewidth=2)
        plt.title(f"{ticker} — posledních 7 dní")
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
    12:00 Praha – report:
    - earnings dnes/zítra
    - včerejší změny (close vs close)
    - top 1 headline pro každou akcii (rychle)
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
        last, prev, pct = get_yday_change(t)
        if last is None:
            continue
        ed = fmp_next_earnings_date(t)
        if ed == today:
            e_today.append(t)
        elif ed == tomorrow:
            e_tom.append(t)
        rows.append((t, last, pct))

    rows.sort(key=lambda x: abs(x[2]) if x[2] is not None else -1, reverse=True)

    msg = []
    msg.append(f"🕛 REPORT 12:00 ({ts.strftime('%d.%m.%Y %H:%M')})")
    if e_today:
        msg.append("📣 Earnings DNES: " + ", ".join(e_today))
    if e_tom:
        msg.append("⏰ Earnings ZÍTRA: " + ", ".join(e_tom))
    msg.append("")
    msg.append("📌 Včerejší změny (close vs close):")
    for (t, last, pct) in rows[:12]:
        nm = name_for(t)
        if pct is None:
            msg.append(f"• {t} — {nm}: {last:.2f} (n/a)")
        else:
            sign = "+" if pct >= 0 else ""
            msg.append(f"• {t} — {nm}: {last:.2f} ({sign}{pct:.2f}%) {bar(pct)}")
    msg.append("")
    msg.append("📰 Top zprávy (1 headline / ticker):")
    for (t, _, _) in rows[:8]:
        news = combined_news(t, 1)
        if news:
            src, title, link = news[0]
            msg.append(f"• {t} [{src}]: {title}")
        else:
            msg.append(f"• {t}: (žádné nové titulky)")

    send_telegram_long("\n".join(msg))

    STATE["premarket_sent_date"] = today_str
    save_json(STATE_FILE, STATE)


def alerts_job():
    """
    12:00–21:00 Praha – každých 15 min.
    Alerty ±3 % od dnešního intraday OPEN (5m data), pokud dostupné.
    Anti-spam: 1× UP a 1× DOWN za den pro ticker.
    """
    ts = now_local()
    if not in_window(ts, ALERT_START, ALERT_END):
        return

    today_str = ts.strftime("%Y-%m-%d")
    sent_today = STATE["alerts_sent"].get(today_str, {})

    for t in PORTFOLIO:
        oc = intraday_open_last(t)
        if not oc:
            continue
        o, last = oc
        pct = pct_change(last, o)
        if pct is None or abs(pct) < ALERT_THRESHOLD:
            continue

        sign_key = "UP" if pct > 0 else "DOWN"
        key = f"{t}:{sign_key}"
        if sent_today.get(key):
            continue

        arrow = "📈" if pct > 0 else "📉"
        nm = name_for(t)
        send_telegram(
            f"🚨 ALERT {arrow}  {t}\n"
            f"{nm}\n"
            f"Změna od dnešního OPEN: {pct:+.2f}% {bar(pct)}\n"
            f"Aktuálně: {last:.2f}\n"
            f"Čas: {ts.strftime('%H:%M')}"
        )
        sent_today[key] = True

    STATE["alerts_sent"][today_str] = sent_today
    save_json(STATE_FILE, STATE)


def build_opportunities():
    """
    PRO výběr: z watchlistu AI/čipy/kovy vezmeme TOP dle absolutní včerejší změny
    + přidáme 1 headline.
    """
    rows = []
    for t in OPPORTUNITY_WATCHLIST:
        last, prev, pct = get_yday_change(t)
        if last is None:
            continue
        score = abs(pct) if pct is not None else 0
        rows.append((t, last, pct, score))
    rows.sort(key=lambda x: x[3], reverse=True)
    return rows[:OPPORTUNITY_MAX]


def evening_job():
    """
    20:00 Praha – večerní shrnutí + email 1× denně
    """
    ts = now_local()
    today_str = ts.strftime("%Y-%m-%d")

    if STATE.get("evening_sent_date") == today_str and (not EMAIL_ENABLED or STATE.get("email_sent_date") == today_str):
        return
    if not after_time(ts, EVENING_TIME):
        return

    # Telegram evening 1× denně
    if STATE.get("evening_sent_date") != today_str:
        opp = build_opportunities()
        msg = []
        msg.append(f"🕗 VEČERNÍ SHRNUTÍ ({ts.strftime('%d.%m.%Y %H:%M')})")
        msg.append("💡 Příležitosti (AI / čipy / kovy) – TOP výběr:")
        msg.append("")
        for (t, last, pct, _) in opp:
            nm = name_for(t)
            if pct is None:
                msg.append(f"• {t} — {nm}: {last:.2f} (n/a)")
            else:
                sign = "+" if pct >= 0 else ""
                msg.append(f"• {t} — {nm}: {last:.2f} ({sign}{pct:.2f}%) {bar(pct)}")
            n = combined_news(t, 1)
            if n:
                src, title, link = n[0]
                msg.append(f"  - [{src}] {title}")
        send_telegram_long("\n".join(msg))

        STATE["evening_sent_date"] = today_str
        save_json(STATE_FILE, STATE)

    # Email digest 1× denně
    if EMAIL_ENABLED and STATE.get("email_sent_date") != today_str:
        send_daily_email_digest(ts)
        STATE["email_sent_date"] = today_str
        save_json(STATE_FILE, STATE)


def send_daily_email_digest(ts: datetime):
    def color(p):
        if p is None:
            return "#555"
        return "#1f8b4c" if p >= 0 else "#c0392b"

    # Portfolio řádky
    rows = []
    for t in PORTFOLIO:
        last, prev, pct = get_yday_change(t)
        if last is None:
            continue
        rows.append((t, last, prev, pct))
    rows.sort(key=lambda x: abs(x[3]) if x[3] is not None else -1, reverse=True)

    today = date.today()
    tomorrow = today + timedelta(days=1)
    e_today, e_tom = [], []
    for t in PORTFOLIO:
        ed = fmp_next_earnings_date(t)
        if ed == today:
            e_today.append(t)
        elif ed == tomorrow:
            e_tom.append(t)

    opp = build_opportunities()

    # Grafy top 12
    inline = {}
    for (t, _, _, _) in rows[:12]:
        path = os.path.join(STATE_DIR, f"chart_{t}.png")
        p = make_chart_7d(t, path)
        if p:
            inline[f"chart_{t}"] = p

    # HTML
    html = []
    html.append(f"<h2>Denní report — {ts.strftime('%d.%m.%Y %H:%M')} ({TIMEZONE})</h2>")
    html.append("<p><b>Ceny:</b> Yahoo (yfinance) | <b>News:</b> Yahoo RSS, SeekingAlpha RSS, GoogleNews RSS | <b>Earnings:</b> FMP calendar</p>")

    if e_today or e_tom:
        html.append("<h3>Earnings</h3>")
        if e_today:
            html.append("<p><b>Dnes:</b> " + ", ".join(e_today) + "</p>")
        if e_tom:
            html.append("<p><b>Zítra:</b> " + ", ".join(e_tom) + "</p>")

    html.append("<h3>Portfolio — včerejší změna</h3>")
    html.append("""
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px;">
<tr style="background:#f2f2f2;">
  <th>Ticker</th><th>Firma</th><th>Close</th><th>Předchozí</th><th>Změna</th><th>Graf</th>
</tr>
""")
    for (t, last, prev, pct) in rows:
        nm = name_for(t)
        prev_str = f"{prev:.2f}" if prev is not None else "—"
        if pct is None:
            change_str = "n/a"
        else:
            sign = "+" if pct >= 0 else ""
            change_str = f"{sign}{pct:.2f}%"
        cid = f"chart_{t}"
        img_html = f'<img src="cid:{cid}" width="320" style="display:block;">' if cid in inline else "—"

        html.append(f"""
<tr>
  <td><b>{t}</b></td>
  <td>{nm}</td>
  <td>{last:.2f}</td>
  <td>{prev_str}</td>
  <td style="color:{color(pct)};"><b>{change_str}</b></td>
  <td>{img_html}</td>
</tr>
""")
    html.append("</table>")

    html.append(f"<h3>Příležitosti (AI / čipy / kovy) — TOP {OPPORTUNITY_MAX}</h3><ul>")
    for (t, last, pct, _) in opp:
        nm = name_for(t)
        if pct is None:
            html.append(f"<li><b>{t}</b> — {nm}: {last:.2f} (n/a)</li>")
        else:
            sign = "+" if pct >= 0 else ""
            html.append(f"<li><b>{t}</b> — {nm}: {last:.2f} (<span style='color:{color(pct)}'><b>{sign}{pct:.2f}%</b></span>)</li>")
            n = combined_news(t, 1)
            if n:
                src, title, link = n[0]
                if link:
                    html.append(f"<ul><li>{src}: <a href='{link}'>{title}</a></li></ul>")
    html.append("</ul>")

    subject = f"Denní report {ts.strftime('%Y-%m-%d')} — portfolio + news + earnings + příležitosti"
    send_email_html(subject, "\n".join(html), inline)


def main():
    # 12:00 report
    premarket_job()

    # 12:00–21:00 alert checks (reálné intraday, když Yahoo dá data)
    alerts_job()

    # 20:00 evening summary + email digest 1× denně
    evening_job()


if __name__ == "__main__":
    main()
