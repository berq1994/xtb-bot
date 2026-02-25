# ahoj.py
from __future__ import annotations

import os
import json
import smtplib
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Dict, List, Any, Optional

import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    import yaml
except Exception:
    yaml = None

import yfinance as yf

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

def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


# ============================================================
# PATHS / STATE (local .state folder)
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_EMAIL_DATE_FILE = os.path.join(STATE_DIR, "last_email_date.txt")

ALERT_DEDUPE_FILE = os.path.join(STATE_DIR, "alert_dedupe.json")  # { "TICKER": {"d":"YYYY-MM-DD","k":"key"} }

def read_text(path: str, default: str = "") -> str:
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
# CONFIG (config.yml)
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
# RUNTIME SETTINGS (env override)
# ============================================================
RUN_MODE = (os.getenv("RUN_MODE") or "run").strip().lower()  # run | learn | backfill

# ✅ defaultně 07:30 (jak chceš)
PREMARKET_TIME = os.getenv("PREMARKET_TIME", str(CFG.get("premarket_time") or "07:30")).strip()
EVENING_TIME   = os.getenv("EVENING_TIME",   str(CFG.get("evening_time")   or "20:00")).strip()

ALERT_START = os.getenv("ALERT_START", str(CFG.get("alert_start") or "12:00")).strip()
ALERT_END   = os.getenv("ALERT_END",   str(CFG.get("alert_end")   or "21:00")).strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", str(CFG.get("alert_threshold_pct") or "3")).strip())

NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", str(CFG.get("news_per_ticker") or "2")).strip())
TOP_N = int(os.getenv("TOP_N", str(CFG.get("top_n") or "5")).strip())


# ============================================================
# TELEGRAM (Secrets)
# ============================================================
TELEGRAM_TOKEN = (os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
CHAT_ID = str(os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or "").strip()
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram není nastavený (token/chat_id).")
        return
    try:
        r = requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=35,
        )
        if r.status_code != 200:
            print("Telegram status:", r.status_code)
            print("Telegram odpověď:", r.text[:500])
    except Exception as e:
        print("Telegram error:", e)

def telegram_send_long(text: str, limit: int = 3500):
    buf = ""
    for line in text.splitlines(True):
        if len(buf) + len(line) > limit:
            telegram_send(buf)
            buf = ""
        buf += line
    if buf.strip():
        telegram_send(buf)


# ============================================================
# EMAIL (1× denně)
# ============================================================
EMAIL_ENABLED = (os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true")
EMAIL_SENDER = (os.getenv("EMAIL_SENDER") or "").strip()
EMAIL_RECEIVER = (os.getenv("EMAIL_RECEIVER") or "").strip()
GMAILPASSWORD = (os.getenv("GMAILPASSWORD") or "").strip()

def email_send(subject: str, body_text: str):
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

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=40)
        server.ehlo()
        server.starttls()
        server.login(EMAIL_SENDER, GMAILPASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print("✅ Email OK")
    except Exception as e:
        print("❌ Email ERROR:", repr(e))


# ============================================================
# Company name (full name) – cache
# ============================================================
_NAME_CACHE: Dict[str, str] = {}

def _company_name_from_yahoo(yahoo_ticker: str) -> str:
    # Caching: na jeden běh workflow to stačí
    if yahoo_ticker in _NAME_CACHE:
        return _NAME_CACHE[yahoo_ticker]
    name = ""
    try:
        info = yf.Ticker(yahoo_ticker).info or {}
        name = (info.get("longName") or info.get("shortName") or "").strip()
    except Exception:
        name = ""
    if not name:
        name = yahoo_ticker
    _NAME_CACHE[yahoo_ticker] = name
    return name


# ============================================================
# REPORTING – format
# ============================================================
def _arrow(p: Optional[float]) -> str:
    if p is None:
        return "•"
    return "🟢▲" if p >= 0 else "🔴▼"

def _bar(p: Optional[float], width: int = 14) -> str:
    if p is None:
        return "—"
    a = min(abs(p), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)

def _fmt_pct(p: Optional[float]) -> str:
    return "—" if p is None else f"{p:+.2f}%"

def format_radar_report(rows: List[Dict[str, Any]], title: str, now: datetime) -> str:
    regime = rows[0].get("regime") if rows else "—"
    regime_detail = rows[0].get("regime_detail") if rows else ""

    rows_sorted = sorted(rows, key=lambda r: float(r.get("score") or 0.0), reverse=True)
    top = rows_sorted[:TOP_N]
    worst = list(reversed(rows_sorted[-TOP_N:]))

    def block(label: str, items: List[Dict[str, Any]]) -> str:
        out = [label]
        for r in items:
            t = r.get("ticker", "?")
            y = r.get("yahoo") or t
            full = _company_name_from_yahoo(y)
            p