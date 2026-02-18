# ahoj.py
# XTB Bot Alerts – GitHub Actions friendly (stateless run + cache)
# - Alerty ±5 % od dnešního OPEN (market open)
# - Běh jen 15:30–21:00 Praha
# - Volitelně 1× denně email "velký report"

import os
import json
import math
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, date, time as dtime

import requests
import yfinance as yf

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python <3.9 by neměl být v Actions, ale pro jistotu:
    ZoneInfo = None

# =========================
# KONFIG (z ENV / SECRETS)
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAMTOKEN", "").strip()
CHAT_ID = os.getenv("CHATID", "").strip()

FMP_API_KEY = os.getenv("FMPAPIKEY", "").strip()  # zatím nepovinné, do budoucna
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "").strip()
GMAIL_PASSWORD = os.getenv("GMAILPASSWORD", "").strip()

REPORT_TIME_LOCAL = os.getenv("REPORT_TIME", "15:30").strip()  # jen informativní

# Portfolio – můžeš nechat natvrdo nebo přepnout na config.json (níž je připraveno)
PORTFOLIO = [
    "CENX", "S", "NVO", "PYPL", "AMZN", "MSFT", "CVX", "NVDA", "TSM", "CAG",
    "META", "SNDK", "AAPL", "GOOGL", "TSLA", "PLTR", "SPY", "FCX", "IREN"
]

# Celé názvy (tam kde je známe jistě)
COMPANY_NAMES = {
    "CENX": "Centrus Energy",
    "S": "SentinelOne",
    "NVO": "Novo Nordisk",
    "PYPL": "PayPal",
    "AMZN": "Amazon",
    "MSFT": "Microsoft",
    "CVX": "Chevron",
    "NVDA": "NVIDIA",
    "TSM": "Taiwan Semiconductor Manufacturing Co. (TSMC)",
    "CAG": "Conagra Brands",
    "META": "Meta Platforms",
    "SNDK": "Sandisk / Western Digital (ticker se může lišit)",
    "AAPL": "Apple",
    "GOOGL": "Alphabet (Google)",
    "TSLA": "Tesla",
    "PLTR": "Palantir",
    "SPY": "SPDR S&P 500 ETF Trust (SPY)",
    "FCX": "Freeport-McMoRan",
    "IREN": "Iris Energy"
}

# Časové okno (Praha)
WINDOW_START = dtime(15, 30)  # 15:30
WINDOW_END = dtime(21, 0)     # 21:00

# Stav – ukládá se do cache (.state)
STATE_DIR = ".state"
STATE_FILE = os.path.join(STATE_DIR, "state.json")

# =========================
# UTIL
# =========================
def prague_now() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo("Europe/Prague"))

def ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)

def load_state() -> dict:
    ensure_state_dir()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state: dict):
    ensure_state_dir()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram není nastaven (TELEGRAMTOKEN/CHATID).")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    r = requests.post(url, data=payload, timeout=30)
    print("Telegram status:", r.status_code)
    if r.status_code >= 400:
        print("Telegram error body:", r.text)

def send_email(subject: str, body: str):
    if not EMAIL_ENABLED:
        return
    if not (EMAIL_SENDER and EMAIL_RECEIVER and GMAIL_PASSWORD):
        print("⚠️ Email není plně nastaven (EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD).")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_SENDER, GMAIL_PASSWORD)
        smtp.sendmail(EMAIL_SENDER, [EMAIL_RECEIVER], msg.as_string())

# =========================
# DATA (Yahoo)
# =========================
def safe_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return float(x)
    except Exception:
        return None

def fetch_open_and_last(tickers):
    """
    Vrátí dict:
      { "AAPL": {"open": 123.0, "last": 125.0}, ... }
    Používá 1m data pro dnešní den.
    """
    result = {}
    # yfinance download umí více tickerů najednou (rychlejší)
    try:
        data = yf.download(
            tickers=tickers,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False
        )
    except Exception as e:
        print("Chyba při yf.download:", e)
        return result

    for t in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                if t not in data.columns.get_level_values(0):
                    continue
                df = data[t]

            if df is None or df.empty:
                continue

            # první řádek = open svíčky
            open_price = safe_float(df["Open"].iloc[0])
            last_price = safe_float(df["Close"].iloc[-1])

            if open_price is None or last_price is None:
                continue

            result[t] = {"open": open_price, "last": last_price}
        except Exception as e:
            print(f"Chyba při zpracování {t}:", e)

    return result

# =========================
# LOGIKA
# =========================
def in_time_window(now_local: datetime) -> bool:
    t = now_local.time()
    return (t >= WINDOW_START) and (t <= WINDOW_END)

def pct_change(open_price: float, last_price: float) -> float:
    if open_price == 0:
        return 0.0
    return ((last_price - open_price) / open_price) * 100.0

def nice_name(ticker: str) -> str:
    return COMPANY_NAMES.get(ticker, ticker)

def build_alert_message(now_local: datetime, alerts: list) -> str:
    # “lepší grafické znázornění” = čisté bloky + emoji
    header = f"🚨 *ALERT ±5%* ({now_local.strftime('%d.%m.%Y %H:%M')} Praha)\n"
    lines = []
    for a in alerts:
        # a: dict {ticker,name,open,last,chg}
        direction = "🟢" if a["chg"] >= 0 else "🔴"
        lines.append(
            f"{direction} {a['ticker']} — {a['name']}\n"
            f"   Open: {a['open']:.2f} → Now: {a['last']:.2f} USD\n"
            f"   Změna od open: {a['chg']:+.2f}%"
        )
    return header + "\n\n".join(lines)

def build_daily_report(now_local: datetime, snapshot: dict) -> str:
    # Velký report (pro email) – všechny tickery
    lines = []
    lines.append(f"Denní report ({now_local.strftime('%d.%m.%Y')}), časy Praha")
    lines.append(f"Okno alertů: {WINDOW_START.strftime('%H:%M')}–{WINDOW_END.strftime('%H:%M')}")
    lines.append("")
    lines.append("Ticker | Firma | Open | Now | Změna od open")
    lines.append("-" * 70)

    # seřadit podle největší změny
    rows = []
    for t, v in snapshot.items():
        chg = pct_change(v["open"], v["last"])
        rows.append((abs(chg), t, v["open"], v["last"], chg))
    rows.sort(reverse=True)

    for _, t, op, last, chg in rows:
        lines.append(
            f"{t:5} | {nice_name(t)} | {op:.2f} | {last:.2f} | {chg:+.2f}%"
        )

    return "\n".join(lines)

def main():
    now = prague_now()
    state = load_state()

    # 1) pojistka – mimo okno neřešíme alerty (ale můžeme poslat email report jednou denně)
    if not in_time_window(now):
        print("Mimo časové okno alertů (Praha).")

        # email report – max 1× denně, po 21:00 klidně
        if EMAIL_ENABLED:
            last_email_date = state.get("last_email_date")
            today = now.date().isoformat()
            if last_email_date != today and now.time() >= WINDOW_END:
                snapshot = fetch_open_and_last(PORTFOLIO)
                if snapshot:
                    body = build_daily_report(now, snapshot)
                    send_email(
                        subject=f"Denní report {now.strftime('%d.%m.%Y')}",
                        body=body
                    )
                    state["last_email_date"] = today
                    save_state(state)
                    print("✅ Email report odeslán.")
        return

    # 2) stáhnout open+last pro celý watchlist
    snapshot = fetch_open_and_last(PORTFOLIO)
    if not snapshot:
        print("⚠️ Nepřišla žádná data z Yahoo.")
        return

    # 3) spočítat alerty ±5%
    alerts = []
    for t, v in snapshot.items():
        chg = pct_change(v["open"], v["last"])
        if abs(chg) >= 5.0:
            alerts.append({
                "ticker": t,
                "name": nice_name(t),
                "open": v["open"],
                "last": v["last"],
                "chg": chg
            })

    # 4) anti-spam: neposílat stejné alerty pořád dokola
    # ukládáme "alert_signature" pro aktuální 15min bucket
    bucket = now.strftime("%Y-%m-%d %H:%M")
    # bucket zaokrouhlíme na 15 minut (aby se při dvojím cron běhu nespamovalo)
    minute = (now.minute // 15) * 15
    bucket = now.replace(minute=minute, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")

    last_bucket_sent = state.get("last_bucket_sent")
    last_signature = state.get("last_signature")

    signature = "|".join(sorted([f"{a['ticker']}:{round(a['chg'],2)}" for a in alerts])) if alerts else ""

    if alerts:
        if last_bucket_sent == bucket and last_signature == signature:
            print("Stejný alert už byl v tomto 15min okně poslaný – neodesílám znovu.")
        else:
            msg = build_alert_message(now, alerts)
            # Telegram neumí MarkdownV2 bez escapování; posíláme plain text:
            msg_plain = msg.replace("*", "")
            telegram_send(msg_plain)
            state["last_bucket_sent"] = bucket
            state["last_signature"] = signature
            save_state(state)
            print(f"✅ Odesláno alertů: {len(alerts)}")
    else:
        print("Hotovo. Odesláno alertů: 0")

    # 5) Email report (max 1× denně) – po 21:00 nebo kdy chceš; tady nechávám po 21:00
    # (aby se to neposílalo uprostřed dne)
    if EMAIL_ENABLED and now.time() >= WINDOW_END:
        today = now.date().isoformat()
        if state.get("last_email_date") != today:
            body = build_daily_report(now, snapshot)
            send_email(
                subject=f"Denní report {now.strftime('%d.%m.%Y')}",
                body=body
            )
            state["last_email_date"] = today
            save_state(state)
            print("✅ Email report odeslán.")

if __name__ == "__main__":
    main()
