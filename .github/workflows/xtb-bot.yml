import os
import json
import math
import pytz
import requests
import feedparser
import yfinance as yf
from datetime import datetime, date, timedelta

# ===== Email (volitelné) =====
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


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
PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()   # report ve 12:00
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()       # večerní shrnutí ve 20:00
ALERT_START = os.getenv("ALERT_START", "12:00").strip()         # kontrola od 12:00
ALERT_END = os.getenv("ALERT_END", "21:00").strip()             # kontrola do 21:00
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3"))       # %

NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2"))
OPPORTUNITY_MAX = int(os.getenv("OPPORTUNITY_MAX", "5"))

# Portfolio
PORTFOLIO_ENV = os.getenv("PORTFOLIO", "").strip()
DEFAULT_PORTFOLIO = [
    "CENX","S","NVO","PYPL","AMZN","MSFT","CVX","NVDA","TSM","CAG","META","AAPL","GOOGL","TSLA",
    "PLTR","SPY","FCX","IREN"
]
PORTFOLIO = [t.strip().upper() for t in PORTFOLIO_ENV.split(",") if t.strip()] if PORTFOLIO_ENV else DEFAULT_PORTFOLIO

# Watchlist příležitostí (AI / čipy / kovy)
OPPORTUNITY_WATCHLIST = [
    # AI / čipy
    "NVDA","TSM","ASML","AMD","AVGO","MU","ARM","INTC","QCOM","SMCI",
    # cloud / AI infra
    "AMZN","MSFT","GOOGL",
    # kovy / těžba
    "FCX","RIO","BHP","SCCO","AA","CENX","TECK"
]

# ===== Scoring váhy =====
SCORE_WEIGHTS = {
    "move": 1.0,      # |%| včera
    "volume": 0.7,    # volume spike
    "news": 0.4,      # news count
    "earnings": 0.6,  # blízkost earnings
}

# =========================
# FIRMY: název + sektor + teze
# =========================
COMPANY = {
    "NVDA": ("NVIDIA", "AI/Čipy", "Lídr v AI akcelerátorech (GPU) a ekosystému CUDA. Těží z růstu AI výpočtů v datacentrech."),
    "TSM": ("TSMC", "Čipy", "Nejdůležitější světový foundry výrobce čipů. Kritický dodavatel špičkových čipů pro AI/mobil/server."),
    "ASML": ("ASML", "Čipy", "Klíčový dodavatel EUV litografie. Bez ASML nelze vyrábět nejmodernější čipy; silná bariéra vstupu."),
    "AMD": ("AMD", "AI/Čipy", "CPU/GPU pro servery a AI. Potenciál růstu v datacentrech a AI akcelerátorech."),
    "AVGO": ("Broadcom", "Čipy/Infra", "Síťové čipy a infrastruktura pro datacentra + software. Těží z růstu AI konektivity."),
    "MU": ("Micron", "Čipy", "Paměti (DRAM/NAND) a HBM pro AI. AI zvyšuje poptávku po pamětech; cyklické, ale s potenciálem."),
    "ARM": ("Arm", "Čipy", "IP architektury CPU (licencování). Expozice na růst ARM v mobilech i serverech/AI edge."),
    "INTC": ("Intel", "Čipy", "Obratový příběh: foundry ambice + produktové cykly. Vyšší riziko, ale případně velká páka na úspěch."),
    "QCOM": ("Qualcomm", "Čipy", "Chipy pro mobil/edge; trend AI on-device. Těží z AI funkcí v telefonech a embedded."),
    "SMCI": ("Super Micro Computer", "AI/Infra", "Serverová infrastruktura (AI servery). Těží z capex hyperscalerů do AI clusterů."),

    "MSFT": ("Microsoft", "Cloud/AI", "Azure cloud + AI integrace do produktů. Stabilní cashflow, AI monetizace přes enterprise."),
    "AMZN": ("Amazon", "Cloud/AI", "AWS je páteř cloudu. AI workloady zvyšují poptávku po výpočetním výkonu a službách."),
    "GOOGL": ("Alphabet (Google)", "Cloud/AI", "AI modely + Google Cloud + reklama. Kombinace AI inovace a robustního byznysu."),

    "FCX": ("Freeport-McMoRan", "Kovy", "Měď jako páteř elektrifikace (sítě, datacentra, EV). Dlouhodobá teze na růst poptávky."),
    "RIO": ("Rio Tinto", "Kovy", "Diverzifikovaná těžba. Expozice na průmyslové kovy a komoditní cyklus."),
    "BHP": ("BHP", "Kovy", "Globální těžař s diverzifikací. Profit z komoditního cyklu a dlouhodobé poptávky po surovinách."),
    "SCCO": ("Southern Copper", "Kovy", "Silná expozice na měď. Benefituje z dlouhodobého trendu elektrifikace."),
    "AA": ("Alcoa", "Kovy", "Hliník – lehký kov pro průmysl. Citlivé na cyklus a ceny energií."),
    "CENX": ("Century Aluminum", "Kovy", "Hliník; cyklické. Potenciál při růstu cen hliníku a zlepšení marží."),
    "TECK": ("Teck Resources", "Kovy", "Těžba kovů/komodit. Expozice na průmyslové kovy."),

    # portfolio navíc
    "META": ("Meta Platforms", "Tech/AI", "Reklama + AI optimalizace + platformy. Silná ziskovost, AI zvyšuje efektivitu."),
    "TSLA": ("Tesla", "Tech/EV", "EV + software + energie. Vysoce volatilní; teze na inovace a škálování."),
    "PLTR": ("Palantir", "AI/Software", "Datová analytika a AI platformy pro enterprise/government. Těží z adopce AI v organizacích."),
    "SPY": ("SPDR S&P 500 ETF", "ETF", "Jádro portfolia: široká diverzifikace, nižší riziko než jednotlivé akcie."),
    "NVO": ("Novo Nordisk", "Health", "Farmacie: GLP-1/obezita a diabetes. Dlouhodobý strukturální růst poptávky."),
    "PYPL": ("PayPal", "Fintech", "Platby/fintech. Obratovka: marže, růst TPV, konkurence; hlídat výsledky a guidance."),
    "CVX": ("Chevron", "Energy", "Energie. Dividendový profil + citlivost na cenu ropy; defenzivnější složka."),
    "CAG": ("Conagra Brands", "Defenziva", "Potraviny: defenzivní spotřeba. Stabilnější, citlivé na marže/inflaci."),
    "AAPL": ("Apple", "Tech", "Ecosystém hardware+services. Silná značka, cashflow, buybacky."),
    "S": ("SentinelOne", "Cyber", "Kyberbezpečnost. Růstový sektor; hlídat cash burn, marže a konkurenci."),
    "IREN": ("Iris Energy", "Infra", "Vyšší riziko; expozice na energeticky náročnou infrastrukturu."),
}

def company_name(t: str) -> str:
    return COMPANY.get(t, (t, "—", ""))[0]

def company_sector(t: str) -> str:
    return COMPANY.get(t, (t, "—", ""))[1]

def company_thesis(t: str) -> str:
    return COMPANY.get(t, (t, "—", "Teze není doplněná – lze přidat."))[2]


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
STATE.setdefault("premarket_sent_date", None)
STATE.setdefault("evening_sent_date", None)
STATE.setdefault("email_sent_date", None)
STATE.setdefault("alerts_sent", {})  # {YYYY-MM-DD: {"TICKER:UP":true,"TICKER:DOWN":true}}


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

def bar(pct: float) -> str:
    if pct is None:
        return ""
    a = abs(pct)
    blocks = min(10, int(round(a)))  # 0–10%
    return "█" * blocks + "░" * (10 - blocks)

def chunk_telegram(text: str, limit: int = 3500):
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

def clamp(x, lo=0.0, hi=10.0):
    return max(lo, min(hi, x))


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
# Email (volitelné 1× denně)
# =========================
def send_email(subject: str, html_body: str) -> bool:
    if not EMAIL_ENABLED:
        return False
    if not (EMAIL_SENDER and EMAIL_RECEIVER and GMAIL_APP_PASSWORD):
        print("⚠️ Email zapnutý, ale chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    msg.attach(MIMEText("Report je v HTML formátu.", "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

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
# Data: Prices
# =========================
def intraday_open_last(ticker: str):
    """Intraday 5m: (open, last). Když Yahoo nedá data, vrátí None."""
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

def avg_volume_20d(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="2mo", interval="1d")
        if h is None or h.empty or "Volume" not in h:
            return None
        v = h["Volume"].dropna()
        if len(v) < 10:
            return None
        return float(v.tail(20).mean())
    except:
        return None

def last_volume(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="10d", interval="1d")
        if h is None or h.empty or "Volume" not in h:
            return None
        v = h["Volume"].dropna()
        if len(v) < 2:
            return None
        return float(v.iloc[-1])
    except:
        return None


# =========================
# Data: News (RSS)
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
# News → "Proč se to hýbe" heuristika
# =========================
WHY_KEYWORDS = [
    (["earnings", "results", "quarter", "q1", "q2", "q3", "q4", "beat", "miss"], "kvůli výsledkům (earnings) / překvapení oproti očekávání"),
    (["guidance", "outlook", "forecast", "raises", "cuts"], "kvůli výhledu (guidance) / změně očekávání"),
    (["upgrade", "downgrade", "price target", "initiated", "rating"], "kvůli doporučení analytiků (upgrade/downgrade/target)"),
    (["acquire", "acquisition", "merger", "m&a", "deal"], "kvůli M&A / akvizici / transakci"),
    (["sec", "investigation", "lawsuit", "regulator", "antitrust", "ban"], "kvůli regulaci / vyšetřování / právním zprávám"),
    (["contract", "partnership", "agreement", "customer", "orders"], "kvůli zakázkám / partnerství / objednávkám"),
    (["chip", "ai", "gpu", "data center", "datacenter", "semiconductor"], "kvůli AI/čipovým zprávám a sentimentu v sektoru"),
    (["supply", "shortage", "inventory", "production", "factory"], "kvůli supply chain / výrobě / zásobám"),
    (["dividend", "buyback", "repurchase"], "kvůli dividendě nebo buybacku"),
]

def why_moving_from_headlines(news_items):
    if not news_items:
        return "bez jasné zprávy – může jít o sektorový sentiment, technický pohyb nebo širší trh."
    titles = " ".join([t for (_, t, _) in news_items]).lower()
    hits = []
    for keys, reason in WHY_KEYWORDS:
        if any(k in titles for k in keys):
            hits.append(reason)
    if not hits:
        return "bez jasné zprávy – může jít o sektorový sentiment, technický pohyb nebo širší trh."
    # max 2 důvody
    return "; ".join(hits[:2]) + "."

# =========================
# Earnings (FMP)
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

def earnings_days_away(ticker: str):
    ed = fmp_next_earnings_date(ticker)
    if not ed:
        return None
    return (ed - date.today()).days

def earnings_score(days_away: int):
    if days_away is None:
        return 0.0
    if days_away <= 2:
        return 3.0
    if days_away <= 7:
        return 2.0
    if days_away <= 14:
        return 1.0
    return 0.0

def earnings_risk_note(days_away: int):
    if days_away is None:
        return ""
    if days_away <= 2:
        return "⚠️ Earnings do 48h: vyšší riziko gapu a volatility."
    if days_away <= 7:
        return "⚠️ Earnings do týdne: počítej s vyšší volatilitou."
    if days_away <= 14:
        return "ℹ️ Earnings do 2 týdnů: může růst nervozita trhu."
    return ""


# =========================
# SCORING + vysvětlení faktorů
# =========================
def explain_scoring(move_abs, vol_spike, news_count, earn_days):
    parts = []
    if move_abs >= 4:
        parts.append("silný pohyb ceny")
    elif move_abs >= 2:
        parts.append("výraznější pohyb ceny")
    else:
        parts.append("menší pohyb ceny")

    if vol_spike >= 1.8:
        parts.append("výrazně vyšší objem (zájem trhu)")
    elif vol_spike >= 1.2:
        parts.append("vyšší objem než obvykle")
    else:
        parts.append("objem bez výrazného spike")

    if news_count >= 5:
        parts.append("hodně novinek (mediální tlak)")
    elif news_count >= 2:
        parts.append("několik novinek")
    else:
        parts.append("málo novinek")

    if earn_days is not None:
        if earn_days <= 2:
            parts.append("earnings velmi blízko (risk/gap)")
        elif earn_days <= 7:
            parts.append("earnings v týdnu")
        elif earn_days <= 14:
            parts.append("earnings do 2 týdnů")

    return ", ".join(parts) + "."


def build_opportunities_scored():
    rows = []
    for t in OPPORTUNITY_WATCHLIST:
        last, prev, pct = get_yday_change(t)
        if last is None:
            continue

        move_abs = abs(pct) if pct is not None else 0.0

        av = avg_volume_20d(t)
        lv = last_volume(t)
        vol_spike = (lv / av) if (av and lv and av > 0) else 1.0

        news_items = combined_news(t, NEWS_PER_TICKER)
        news_count = float(len(news_items))

        d = earnings_days_away(t)
        e_score = earnings_score(d)

        score = (
            SCORE_WEIGHTS["move"] * clamp(move_abs, 0, 10) +
            SCORE_WEIGHTS["volume"] * clamp(vol_spike, 0, 5) +
            SCORE_WEIGHTS["news"] * clamp(news_count, 0, 6) +
            SCORE_WEIGHTS["earnings"] * clamp(e_score, 0, 3)
        )

        rows.append({
            "ticker": t,
            "name": company_name(t),
            "sector": company_sector(t),
            "thesis": company_thesis(t),
            "last": last,
            "pct": pct,
            "score": score,
            "move_abs": move_abs,
            "vol_spike": vol_spike,
            "news_count": int(news_count),
            "earn_days": d,
            "risk_note": earnings_risk_note(d),
            "news_items": news_items,
            "top_news": (news_items[0] if news_items else None),
            "why_move": why_moving_from_headlines(news_items),
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:OPPORTUNITY_MAX]


# =========================
# JOBS
# =========================
def premarket_job():
    """12:00 Praha – report: earnings dnes/zítra, včerejší změny, top titulky."""
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
    msg.append("⚠️ Informativní přehled (ne investiční doporučení).")
    msg.append("")
    if e_today:
        msg.append("📣 Earnings DNES: " + ", ".join(e_today))
    if e_tom:
        msg.append("⏰ Earnings ZÍTRA: " + ", ".join(e_tom))
    msg.append("")
    msg.append("📌 Včerejší změny (close vs close):")
    for (t, last, pct) in rows[:12]:
        nm = company_name(t)
        sec = company_sector(t)
        if pct is None:
            msg.append(f"• {t} — {nm} [{sec}]: {last:.2f} (n/a)")
        else:
            sign = "+" if pct >= 0 else ""
            msg.append(f"• {t} — {nm} [{sec}]: {last:.2f} ({sign}{pct:.2f}%) {bar(pct)}")

    msg.append("")
    msg.append("📰 Top titulky (1 headline / ticker):")
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
    12:00–21:00 Praha – kontrola.
    Alerty ±3 % od dnešního OPEN (intraday 5m) – pokud Yahoo dá intraday.
    Anti-spam: max 1× UP a 1× DOWN za ticker za den.
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

        direction = "UP" if pct > 0 else "DOWN"
        key = f"{t}:{direction}"
        if sent_today.get(key):
            continue

        arrow = "📈" if pct > 0 else "📉"
        nm = company_name(t)
        sec = company_sector(t)
        send_telegram(
            f"🚨 ALERT {arrow} {t}\n"
            f"{nm} [{sec}]\n"
            f"Změna od dnešního OPEN: {pct:+.2f}% {bar(pct)}\n"
            f"Aktuální cena: {last:.2f}\n"
            f"Čas: {ts.strftime('%H:%M')}"
        )
        sent_today[key] = True

    STATE["alerts_sent"][today_str] = sent_today
    save_json(STATE_FILE, STATE)


def evening_job():
    """
    20:00 Praha – 1× denně:
    TOP 5 příležitostí se scoringem + odůvodnění + co firma dělá + proč může být úspěšná + "proč se to hýbe".
    Volitelně i email 1× denně.
    """
    ts = now_local()
    today_str = ts.strftime("%Y-%m-%d")

    if not after_time(ts, EVENING_TIME):
        return

    opp = build_opportunities_scored()

    # Telegram 1× denně
    if STATE.get("evening_sent_date") != today_str:
        msg = []
        msg.append(f"🕗 VEČERNÍ SHRNUTÍ ({ts.strftime('%d.%m.%Y %H:%M')})")
        msg.append("💡 TOP příležitosti (AI / čipy / kovy) – SCORING")
        msg.append("SCORE = pohyb + volume spike + news + blízkost earnings")
        msg.append("⚠️ Informativní přehled (ne investiční doporučení).")
        msg.append("")

        for r in opp:
            t = r["ticker"]
            nm = r["name"]
            sec = r["sector"]
            last = r["last"]
            pct = r["pct"]
            score = r["score"]
            arrow = "📈" if (pct is not None and pct >= 0) else "📉"

            if pct is None:
                head = f"{arrow} {t} — {nm} [{sec}] | {last:.2f} | SCORE {score:.2f}"
            else:
                sign = "+" if pct >= 0 else ""
                head = f"{arrow} {t} — {nm} [{sec}] | {last:.2f} ({sign}{pct:.2f}%) {bar(pct)} | SCORE {score:.2f}"

            msg.append(head)
            msg.append(f"• Proč je to v TOP: {explain_scoring(r['move_abs'], r['vol_spike'], r['news_count'], r['earn_days'])}")
            if r["risk_note"]:
                msg.append(f"• Riziko: {r['risk_note']}")
            msg.append(f"• Co firma dělá / proč může být úspěšná: {r['thesis']}")
            msg.append(f"• Proč se to dnes/trhem hýbalo (z headline): {r['why_move']}")

            if r["top_news"]:
                src, title, link = r["top_news"]
                msg.append(f"• Top zpráva: [{src}] {title}")

            msg.append("")

        send_telegram_long("\n".join(msg))
        STATE["evening_sent_date"] = today_str
        save_json(STATE_FILE, STATE)

    # Email 1× denně (pokud zapnuto)
    if EMAIL_ENABLED and STATE.get("email_sent_date") != today_str:
        html = []
        html.append(f"<h2>Večerní shrnutí (SCORING) — {ts.strftime('%d.%m.%Y %H:%M')} ({TIMEZONE})</h2>")
        html.append("<p><b>Upozornění:</b> Informativní přehled, ne investiční doporučení.</p>")
        html.append("<ol>")
        for r in opp:
            t = r["ticker"]
            nm = r["name"]
            sec = r["sector"]
            pct = r["pct"]
            pct_txt = "n/a" if pct is None else f"{pct:+.2f}%"
            html.append(f"<li><b>{t}</b> — {nm} <i>({sec})</i> | SCORE {r['score']:.2f} | změna {pct_txt}<br>")
            html.append(f"<b>Teze:</b> {r['thesis']}<br>")
            html.append(f"<b>Proč v TOP:</b> {explain_scoring(r['move_abs'], r['vol_spike'], r['news_count'], r['earn_days'])}<br>")
            if r["risk_note"]:
                html.append(f"<b>Riziko:</b> {r['risk_note']}<br>")
            html.append(f"<b>Proč se to hýbe:</b> {r['why_move']}<br>")
            if r["top_news"]:
                src, title, link = r["top_news"]
                html.append(f"<b>Top zpráva:</b> [{src}] <a href='{link}'>{title}</a>")
            html.append("</li><br>")
        html.append("</ol>")

        subject = f"Večerní shrnutí (SCORING) {today_str}"
        send_email(subject, "\n".join(html))
        STATE["email_sent_date"] = today_str
        save_json(STATE_FILE, STATE)


def main():
    premarket_job()
    alerts_job()
    evening_job()


if __name__ == "__main__":
    main()
