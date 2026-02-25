from __future__ import annotations

import os
import requests
import smtplib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Any

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    import yaml
except Exception:
    yaml = None


# ============================================================
# CONFIG
# ============================================================
def load_cfg() -> dict:
    if yaml is None:
        return {}
    try:
        with open("config.yml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

CFG = load_cfg()

def cfg_get(path: str, default=None):
    cur = CFG
    try:
        for p in path.split("."):
            if not isinstance(cur, dict):
                return default
            cur = cur.get(p)
        return default if cur is None else cur
    except Exception:
        return default


# ============================================================
# ENV
# ============================================================
TZ_NAME = os.getenv("TIMEZONE", "Europe/Prague")
TZ = ZoneInfo(TZ_NAME)

RUN_MODE = (os.getenv("RUN_MODE") or "run").lower()

FMP_API_KEY = (os.getenv("FMPAPIKEY") or cfg_get("fmp_api_key") or "").strip()

TELEGRAM_TOKEN = (os.getenv("TELEGRAMTOKEN") or "").strip()
CHAT_ID = (os.getenv("CHATID") or "").strip()

EMAIL_ENABLED = (os.getenv("EMAIL_ENABLED", "false").lower() == "true")
EMAIL_SENDER = (os.getenv("EMAIL_SENDER") or "").strip()
EMAIL_RECEIVER = (os.getenv("EMAIL_RECEIVER") or "").strip()
GMAILPASSWORD = (os.getenv("GMAILPASSWORD") or "").strip()

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ============================================================
# HELPERS
# ============================================================
def now_local() -> datetime:
    return datetime.now(TZ)

def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram není nastaven.")
        return
    try:
        requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=30
        )
    except Exception as e:
        print("Telegram error:", e)

def email_send(subject: str, body: str):
    if not EMAIL_ENABLED:
        return
    if not (EMAIL_SENDER and EMAIL_RECEIVER and GMAILPASSWORD):
        print("Email není správně nastaven.")
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, GMAILPASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
    except Exception as e:
        print("Email error:", e)


# ============================================================
# FMP Earnings
# ============================================================
def fmp_earnings_week(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    if not FMP_API_KEY:
        return []

    url = "https://financialmodelingprep.com/api/v3/earning_calendar"
    try:
        r = requests.get(url, params={
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
            "apikey": FMP_API_KEY
        }, timeout=30)

        if r.status_code != 200:
            return []

        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []


def format_earnings_table(rows: List[Dict[str, Any]], week_start: datetime) -> str:
    out = []
    out.append(f"📅 EARNINGS TÝDEN ({week_start.strftime('%d.%m.%Y')})")
    out.append("")

    if not rows:
        out.append("Žádné earnings události.")
        return "\n".join(out)

    for r in rows[:25]:
        ticker = r.get("symbol")
        name = r.get("name")
        date = r.get("date")
        eps = r.get("epsEstimated")

        out.append(f"{date} | {ticker}")
        if name:
            out.append(f"   {name}")
        if eps:
            out.append(f"   Oček. EPS: {eps}")
        out.append("")

    return "\n".join(out)


# ============================================================
# MAIN
# ============================================================
def run_weekly_earnings():
    now = now_local()
    week_start = now
    week_end = now + timedelta(days=7)

    data = fmp_earnings_week(week_start, week_end)
    msg = format_earnings_table(data, week_start)

    telegram_send(msg)
    email_send(f"EARNINGS TÝDEN ({week_start.strftime('%d.%m.%Y')})", msg)

    print("✅ Weekly earnings hotovo.")


def main():
    print(f"RUN_MODE = {RUN_MODE}")

    if RUN_MODE == "earnings":
        run_weekly_earnings()
        return

    print("Standardní běh – earnings se nespouští.")


if __name__ == "__main__":
    main()