from __future__ import annotations

import os
import json
import smtplib
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Dict, List, Any

import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    import yaml
except Exception:
    yaml = None

from radar.engine import run_radar_snapshot, run_alerts_snapshot


# ============================================================
# TIMEZONE
# ============================================================
TZ_NAME = os.getenv("TIMEZONE", "Europe/Prague").strip()
TZ = ZoneInfo(TZ_NAME)

def now_local() -> datetime:
    return datetime.now(TZ)

def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")

def dt_to_date(dt: datetime) -> date:
    return dt.date()


# ============================================================
# STATE / FILES
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_EMAIL_DATE_FILE = os.path.join(STATE_DIR, "last_email_date.txt")
ALERT_DEDUPE_FILE = os.path.join(STATE_DIR, "alert_dedupe.json")


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


# ============================================================
# CONFIG
# ============================================================
DEFAULT_CONFIG_PATHS = ["config.yml", "config.yaml"]

def load_cfg() -> dict:
    if yaml is None:
        return {}
    for p in DEFAULT_CONFIG_PATHS:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
    return {}

CFG = load_cfg()


# ============================================================
# RUNTIME SETTINGS
# ============================================================
PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()

ALERT_START = os.getenv("ALERT_START", "12:00").strip()
ALERT_END = os.getenv("ALERT_END", "21:00").strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3").strip())


# ============================================================
# TELEGRAM
# ============================================================
TELEGRAM_TOKEN = (os.getenv("TELEGRAMTOKEN") or "").strip()
CHAT_ID = str(os.getenv("CHATID") or "").strip()
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram není nastavený.")
        return
    try:
        requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=35,
        )
    except Exception as e:
        print("Telegram error:", e)


# ============================================================
# EMAIL
# ============================================================
EMAIL_ENABLED = (os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true")
EMAIL_SENDER = (os.getenv("EMAIL_SENDER") or "").strip()
EMAIL_RECEIVER = (os.getenv("EMAIL_RECEIVER") or "").strip()
GMAILPASSWORD = (os.getenv("GMAILPASSWORD") or "").strip()

def email_send(subject: str, body_text: str):
    if not EMAIL_ENABLED:
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, GMAILPASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
    except Exception as e:
        print("Email error:", e)


# ============================================================
# MAIN LOGIC
# ============================================================
def run_reports(cfg: dict, now: datetime):
    today = dt_to_date(now).isoformat()

    if hm(now) == PREMARKET_TIME and read_text(LAST_PREMARKET_DATE_FILE) != today:
        rows = run_radar_snapshot(cfg, now, reason="premarket")
        if rows:
            msg = f"🕛 PREMARKET\nTOP ticker: {rows[0]['ticker']} | score {rows[0]['score']:.2f}"
            telegram_send(msg)
            email_send("Premarket report", msg)
            write_text(LAST_PREMARKET_DATE_FILE, today)

    if hm(now) == EVENING_TIME and read_text(LAST_EVENING_DATE_FILE) != today:
        rows = run_radar_snapshot(cfg, now, reason="evening")
        if rows:
            msg = f"🌙 VEČER\nTOP ticker: {rows[0]['ticker']} | score {rows[0]['score']:.2f}"
            telegram_send(msg)
            write_text(LAST_EVENING_DATE_FILE, today)


def run_alerts(cfg: dict, now: datetime):
    if not (ALERT_START <= hm(now) <= ALERT_END):
        return

    alerts = run_alerts_snapshot(cfg, now, st=None)

    for a in alerts:
        telegram_send(f"🚨 {a['ticker']} {a['pct_from_open']:+.2f}%")


def main():
    now = now_local()
    print(f"✅ Bot běží | {now.strftime('%H:%M')}")

    run_reports(CFG, now)
    run_alerts(CFG, now)


if __name__ == "__main__":
    main()