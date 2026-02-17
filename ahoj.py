import os
import json
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

import requests
import yfinance as yf
import feedparser

# překlad headline do CZ (když není deep_translator, jede bez překladu)
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

# časová zóna CZ
try:
    from zoneinfo import ZoneInfo
    CZ_TZ = ZoneInfo("Europe/Prague")
except Exception:
    CZ_TZ = None

# =======================
# SECRETS z GitHubu (ty už máš uložené)
# =======================
TELEGRAMTOKEN = os.getenv("TELEGRAMTOKEN", "").strip()
CHATID = os.getenv("CHATID", "").strip()

FMPAPIKEY = os.getenv("FMPAPIKEY", "").strip()  # zatím nevyužito, necháváme do budoucna

GMAILPASSWORD = os.getenv("GMAILPASSWORD", "").replace(" ", "").strip()
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "berq1994@gmail.com").strip()
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "berq1994@gmail.com").strip()
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() in ("1", "true", "yes", "y")

# =======================
# PORTFOLIO + WATCHLIST (Hybrid)
# =======================
PORTFOLIO = [
    "CENX", "S", "NVO", "PYPL", "AMZN", "MSFT",
    "CVX", "NVDA", "TSM", "CAG", "META", "SNDK", "AAPL", "GOOGL", "TSLA",
    "PLTR", "SPY", "FCX", "IREN"
]

WATCHLIST = [
    "SNOW", "DDOG", "CRWD", "MDB",
    "AMD", "AVGO", "ASML", "LRCX", "AMAT", "MU",
    "SCCO", "TECK", "COPX"
]

# =======================
# STATE (kvůli tomu, aby to neběželo 2× denně + limit 5/týden)
# Pozn.: GitHub Actions je stateless, ale workflow níže dává cache pro .state/
# =======================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)
LAST_RUN_FILE = os.path.join(STATE_DIR, "last_run_date.txt")
WEEKLY_QUOTA_FILE = os.path.join(STATE_DIR, "weekly_quota.json")
LAST_EMAIL_FILE = os.path.join(STATE_DIR, "last_email_date.txt")


def now_cz():
    if CZ_TZ:
        return datetime.now(tz=CZ_TZ)
    return datetime.now()


def today_key():
    return now_cz().strftime("%Y-%m-%d")


def current_week_key():
    iso = now_cz().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def already_ran_today():
    try:
        with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() == today_key()
    except:
        return False


def mark_ran_today():
    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        f.write(today_key())


# =======================
# TELEGRAM
# =======================
def tg_send(text: str):
    if not TELEGRAMTOKEN or not CHATID:
        print("Chybí TELEGRAMTOKEN nebo CHATID.")
        return
    text = (text or "").strip()
    if not text:
        return

    url = f"https://api.telegram.org/bot{TELEGRAMTOKEN}/sendMessage"
    # Telegram limit – posíláme po blocích
    max_len = 3800
    for i in range(0, len(text), max_len):
        chunk = text[i:i + max_len]
        try:
            r = requests.post(url, data={"chat_id": CHATID, "text": chunk}, timeout=20)
            if r.status_code != 200:
                print("Telegram status:", r.status_code, r.text)
        except Exception as e:
            print("Telegram chyba:", e)


# =======================
# EMAIL (max 1× denně)
# =======================
def already_sent_email_today():
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
    if not EMAIL_SENDER or not EMAIL_RECEIVER or not GMAILPASSWORD:
        print("Email: chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_SENDER, GMAILPASSWORD)
    server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
    server.quit()


# =======================
# DATA
# =======================
def get_price_and_change_pct(ticker: str):
    """
    Změna vůči předchozímu obchodnímu dni.
    Používáme 7d, aby to fungovalo i přes víkendy/svátky.
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
    try:
        feed = feedparser.parse(
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        )
        if not feed.entries:
            return None
        return feed.entries[0].title
    except:
        return None


# =======================
# WEEKLY QUOTA (max 5/týden)
# =======================
def load_weekly_quota():
    key = current_week_key()
    data = {"week_key": key, "remaining": 5}

    if os.path.exists(WEEKLY_QUOTA_FILE):
        try:
            with open(WEEKLY_QUOTA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if loaded.get("week_key") == key:
                data["remaining"] = int(loaded.get("remaining", 5))
        except:
            pass

    data["remaining"] = max(0, min(5, data["remaining"]))
    return data


def save_weekly_quota(data):
    with open(WEEKLY_QUOTA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =======================
# REPORTY
# =======================
def generate_big_report_text():
    now = now_cz().strftime("%d.%m.%Y %H:%M")
    lines = [f"📈 VELKÝ DENNÍ REPORT – {now}", ""]

    spy_price, spy_pct = get_price_and_change_pct("SPY")
    if spy_price is not None:
        lines.append("📌 Trh (SPY)")
        if spy_pct is None:
            lines.append(f"SPY: {spy_price:.2f} USD")
        else:
            lines.append(f"SPY: {spy_price:.2f} USD ({spy_pct:+.2f} %)")
        lines.append("")

    lines.append("📋 Portfolio")
    for tkr in PORTFOLIO:
        price, pct = get_price_and_change_pct(tkr)
        if price is None:
            lines.append(f"{tkr}: (bez dat)")
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


def generate_opportunities_text():
    THRESHOLD = 4.5
    candidates = []

    for tkr in WATCHLIST:
        price, pct = get_price_and_change_pct(tkr)
        if pct is None:
            continue
        if pct >= THRESHOLD or pct <= -THRESHOLD:
            h = get_news_headline(tkr)
            candidates.append({"ticker": tkr, "pct": float(pct), "headline": translate_cs(h) if h else None})

    if not candidates:
        return "📊 Investiční příležitosti dne (WATCHLIST)\n\nDnes žádné silné setupy (±4.5 % a více)."

    candidates.sort(key=lambda x: abs(x["pct"]), reverse=True)

    quota = load_weekly_quota()
    if quota["remaining"] <= 0:
        return (
            "📊 Investiční příležitosti dne (WATCHLIST)\n\n"
            "Limit 5 příležitostí za týden je vyčerpán.\n"
            "Další pošlu až v novém týdnu."
        )

    selected = candidates[:quota["remaining"]]
    quota["remaining"] -= len(selected)
    save_weekly_quota(quota)

    momentum = [x for x in selected if x["pct"] > 0]
    dip = [x for x in selected if x["pct"] < 0]

    lines = ["📊 Investiční příležitosti dne (WATCHLIST)", ""]

    if momentum:
        lines.append("📈 Momentum")
        for x in momentum:
            lines.append(f"• {x['ticker']} ({x['pct']:+.2f} %)")
            if x["headline"]:
                lines.append(f"  📰 {x['headline']}")
        lines.append("")

    if dip:
        lines.append("📉 Dip")
        for x in dip:
            lines.append(f"• {x['ticker']} ({x['pct']:+.2f} %)")
            if x["headline"]:
                lines.append(f"  📰 {x['headline']}")
        lines.append("")

    lines.append(f"🧮 Týdenní limit: zbývá {quota['remaining']} / 5")
    return "\n".join(lines)


def daily_block():
    report = generate_big_report_text()
    opps = generate_opportunities_text()

    tg_send(report)
    tg_send(opps)

    # email max 1× denně
    if EMAIL_ENABLED and not already_sent_email_today():
        try:
            send_email("Velký denní report portfolia", report)
            mark_email_sent_today()
            tg_send("✅ Email: velký denní report byl odeslán (max 1× denně).")
        except Exception as e:
            tg_send(f"⚠️ Email se nepodařilo odeslat: {e}")


def main():
    # spouštíme jen v 15:30 CZ, ale workflow poběží 2× (kvůli letnímu času)
    t = now_cz()
    if t.strftime("%H:%M") != "15:30":
        print("Teď není 15:30 CZ, končím:", t.strftime("%H:%M"))
        return

    if already_ran_today():
        print("Už běželo dnes, končím.")
        return

    daily_block()
    mark_ran_today()


if __name__ == "__main__":
    main()
