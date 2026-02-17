import json
import os
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

import requests
import yfinance as yf
import feedparser
import schedule

# Překlad headline do češtiny (když deep_translator není, jede to bez překladu)
try:
    from deep_translator import GoogleTranslator
    def translate_cs(text: str) -> str:
        try:
            return GoogleTranslator(source="auto", target="cs").translate(text)
        except:
            return text
except Exception:
    def translate_cs(text: str) -> str:
        return text


# =======================
# CONFIG
# =======================
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

TOKEN = CONFIG["telegram_token"]
CHAT_ID = int(CONFIG["chat_id"])
REPORT_TIME = CONFIG.get("report_time", "15:30")

PORTFOLIO = CONFIG.get("portfolio", [])
WATCHLIST = CONFIG.get("watchlist", [])

EMAIL_CFG = CONFIG.get("email", {})
EMAIL_ENABLED = bool(EMAIL_CFG.get("enabled", False))
EMAIL_SENDER = EMAIL_CFG.get("sender", "")
EMAIL_PASSWORD = EMAIL_CFG.get("app_password", "")
EMAIL_RECEIVER = EMAIL_CFG.get("receiver", "")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

TELEGRAM_SEND_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

LAST_EMAIL_FILE = "last_email_date.txt"       # ochrana proti více emailům za den
WEEKLY_QUOTA_FILE = "weekly_opps_quota.json"  # limit 5 příležitostí / týden


# =======================
# TELEGRAM
# =======================
def tg_send(text: str):
    text = (text or "").strip()
    if not text:
        return
    # Telegram limit – raději posílat po částech
    max_len = 3800
    for i in range(0, len(text), max_len):
        chunk = text[i:i + max_len]
        try:
            requests.post(TELEGRAM_SEND_URL, data={"chat_id": CHAT_ID, "text": chunk}, timeout=15)
        except Exception as e:
            print("Telegram chyba:", e)


# =======================
# EMAIL (1× denně max)
# =======================
def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def already_sent_email_today() -> bool:
    try:
        with open(LAST_EMAIL_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() == today_key()
    except:
        return False


def mark_email_sent_today():
    with open(LAST_EMAIL_FILE, "w", encoding="utf-8") as f:
        f.write(today_key())


def send_email(subject: str, body: str):
    if not EMAIL_ENABLED:
        return
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("Email config chybí (sender/app_password/receiver).")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
    server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
    server.quit()


# =======================
# DATA: cena + denní změna (robustní i přes víkend)
# =======================
def get_price_and_change_pct(ticker: str):
    """
    Vrátí (last_close, day_pct) – day_pct je změna vůči předchozímu obchodnímu dni.
    Používá period=7d, aby to fungovalo i přes víkendy/svátky.
    """
    try:
        hist = yf.Ticker(ticker).history(period="7d")
        if hist is None or hist.empty:
            return None, None

        closes = hist["Close"].dropna()
        if len(closes) < 2:
            last = float(closes.iloc[-1])
            return last, None

        prev = float(closes.iloc[-2])
        last = float(closes.iloc[-1])
        pct = ((last - prev) / prev) * 100 if prev != 0 else None
        return last, pct
    except:
        return None, None


def get_news_headline(ticker: str):
    """
    Vezme 1 nejnovější headline z Yahoo RSS.
    """
    try:
        feed = feedparser.parse(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US")
        if not feed.entries:
            return None
        return feed.entries[0].title
    except:
        return None


# =======================
# WEEKLY QUOTA (max 5 příležitostí týdně)
# =======================
def current_week_key() -> str:
    # ISO week: 2026-W07
    iso = datetime.now().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def load_weekly_quota():
    key = current_week_key()
    if os.path.exists(WEEKLY_QUOTA_FILE):
        try:
            with open(WEEKLY_QUOTA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}
    else:
        data = {}

    # reset při změně týdne
    if data.get("week_key") != key:
        data = {"week_key": key, "remaining": 5}

    # pojistky
    if "remaining" not in data:
        data["remaining"] = 5
    data["remaining"] = max(0, int(data["remaining"]))
    return data


def save_weekly_quota(data):
    with open(WEEKLY_QUOTA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =======================
# REPORT (Telegram + Email)
# =======================
def generate_big_report_text():
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    lines = [f"VELKÝ DENNÍ REPORT PORTFOLIA – {now}", "=" * 60, ""]

    # Benchmark SPY (i když není v portfoliu)
    spy_price, spy_pct = get_price_and_change_pct("SPY")
    if spy_price is not None:
        lines.append("📌 Trh (benchmark)")
        if spy_pct is None:
            lines.append(f"SPY: {spy_price:.2f} USD")
        else:
            lines.append(f"SPY: {spy_price:.2f} USD ({spy_pct:+.2f} %)")
        lines.append("")

    lines.append("📋 Portfolio")
    for tkr in PORTFOLIO:
        price, pct = get_price_and_change_pct(tkr)
        if price is None:
            lines.append(f"{tkr}: (bez ceny)")
            lines.append("")
            continue

        if pct is None:
            lines.append(f"{tkr}: {price:.2f} USD")
        else:
            lines.append(f"{tkr}: {price:.2f} USD ({pct:+.2f} %)")

        headline = get_news_headline(tkr)
        if headline:
            lines.append(f"  📰 {translate_cs(headline)}")
        lines.append("")

    return "\n".join(lines)


def send_daily_email_once(report_text: str):
    if not EMAIL_ENABLED:
        return

    if already_sent_email_today():
        print("Email už dnes byl odeslán – přeskočeno.")
        return

    try:
        send_email("Velký denní report portfolia", report_text)
        mark_email_sent_today()
        print("Email odeslán.")
        tg_send("✅ Velký denní report byl odeslán na email (max 1× denně).")
    except Exception as e:
        print("Email chyba:", e)
        tg_send(f"⚠️ Email report se nepodařilo odeslat: {e}")


# =======================
# PŘÍLEŽITOSTI (watchlist) – s důvodem + limit 5/týden
# =======================
def generate_opportunities_text():
    """
    Shrnutí příležitostí dne (WATCHLIST):
    - momentum: >= +4.5 %
    - dip: <= -4.5 %
    U každé: % + headline (důvod).
    Max 5 příležitostí týdně (tvrdý limit).
    """
    THRESHOLD = 4.5

    # nasbírat kandidáty
    candidates = []
    for tkr in WATCHLIST:
        price, pct = get_price_and_change_pct(tkr)
        if pct is None:
            continue
        if pct >= THRESHOLD or pct <= -THRESHOLD:
            headline = get_news_headline(tkr)
            candidates.append({
                "ticker": tkr,
                "pct": float(pct),
                "headline": translate_cs(headline) if headline else None
            })

    if not candidates:
        return "📊 Investiční příležitosti dne (WATCHLIST)\n\nDnes žádné silné setupy (±4.5 % a více)."

    # seřadit podle absolutní velikosti pohybu
    candidates.sort(key=lambda x: abs(x["pct"]), reverse=True)

    # weekly quota
    quota = load_weekly_quota()
    remaining = quota["remaining"]
    if remaining <= 0:
        return (
            "📊 Investiční příležitosti dne (WATCHLIST)\n\n"
            "Limit 5 příležitostí za týden je už vyčerpán.\n"
            "Další příležitosti pošlu až v novém týdnu."
        )

    # vezmeme jen kolik zbývá
    selected = candidates[:remaining]
    quota["remaining"] = remaining - len(selected)
    save_weekly_quota(quota)

    momentum = [x for x in selected if x["pct"] > 0]
    dip = [x for x in selected if x["pct"] < 0]

    lines = ["📊 Investiční příležitosti dne (WATCHLIST)", ""]

    if momentum:
        lines.append("📈 Momentum setupy")
        for x in momentum:
            lines.append(f"• {x['ticker']} ({x['pct']:+.2f} %)")
            if x["headline"]:
                lines.append(f"  📰 {x['headline']}")
        lines.append("")

    if dip:
        lines.append("📉 Dip setupy")
        for x in dip:
            lines.append(f"• {x['ticker']} ({x['pct']:+.2f} %)")
            if x["headline"]:
                lines.append(f"  📰 {x['headline']}")
        lines.append("")

    lines.append(f"🧮 Týdenní limit: zbývá {quota['remaining']} / 5 příležitostí pro tento týden.")
    return "\n".join(lines)


# =======================
# DAILY BLOCK @ 15:30
# =======================
def daily_block():
    report = generate_big_report_text()

    # Telegram: report + opportunities
    tg_send(report)
    tg_send(generate_opportunities_text())

    # Email: jen velký report, max 1× denně
    send_daily_email_once(report)


# =======================
# START
# =======================
schedule.every().day.at(REPORT_TIME).do(daily_block)

print("✅ Bot běží: 15:30 Telegram(report+příležitosti) + Email(report max 1× denně)")

while True:
    schedule.run_pending()
    time.sleep(5)