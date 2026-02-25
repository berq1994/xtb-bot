# ahoj.py
from __future__ import annotations

import os
import json
import math
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

def today_str() -> str:
    return dt_to_date(now_local()).isoformat()

def dt_to_date(dt: datetime) -> date:
    return dt.date()

def is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5

def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


# ============================================================
# PATHS / STATE
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_EMAIL_DATE_FILE = os.path.join(STATE_DIR, "last_email_date.txt")

ALERT_DEDUPE_FILE = os.path.join(STATE_DIR, "alert_dedupe.json")  # { "TICKER": {"d":"YYYY-MM-DD","k":"key"} }

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

def cfg_get(path: str, default=None):
    cur = CFG
    try:
        for part in path.split("."):
            if not isinstance(cur, dict):
                return default
            cur = cur.get(part)
        return default if cur is None else cur
    except Exception:
        return default


# ============================================================
# RUNTIME SETTINGS (env override)
# ============================================================
RUN_MODE = (os.getenv("RUN_MODE") or "run").strip().lower()  # run | learn | backfill (teď používáme run)

PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()

ALERT_START = os.getenv("ALERT_START", "12:00").strip()
ALERT_END = os.getenv("ALERT_END", "21:00").strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3").strip())

NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2").strip())
TOP_N = int(os.getenv("TOP_N", "5").strip())

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
        print("Telegram status:", r.status_code)
        if r.status_code != 200:
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
# REPORTING – „profi“ formát
# ============================================================
def _arrow(p: float | None) -> str:
    if p is None:
        return "•"
    if p >= 0:
        return "🟢▲"
    return "🔴▼"

def _bar(p: float | None, width: int = 14) -> str:
    if p is None:
        return "—"
    a = min(abs(p), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)

def _fmt_pct(p: float | None) -> str:
    return "—" if p is None else f"{p:+.2f}%"

def classify_move(p_from_open: float, why: str) -> str:
    """
    Jednoduchá klasifikace intradenního pohybu:
    - earnings/guidance => Earnings move
    - risk-off => Market risk-off move
    - jinak => Normal move
    """
    w = (why or "").lower()
    a = abs(p_from_open)

    if any(k in w for k in ["earnings", "výsledky", "guidance", "výhled"]):
        if a >= 7:
            return "🧨 Earnings shock"
        return "📊 Earnings move"

    if a >= 6:
        return "⚡ Impulsní pohyb (možný catalyst/news)"
    if a >= 3:
        return "📍 Trendový intradenní pohyb"
    return "• Běžný pohyb"

def format_alert(alert: Dict[str, Any], why: str | None = None) -> str:
    t = alert["ticker"]
    p = alert["pct_from_open"]
    o = alert.get("open")
    last = alert.get("last")
    mv = alert.get("movement") or ""
    tag = classify_move(p, why or "")

    return (
        f"🚨 ALERT ({hm(now_local())})\n"
        f"{_arrow(p)} {t} | od OPEN: {_fmt_pct(p)}  {_bar(p)}\n"
        f"Typ: {tag} | {mv}\n"
        f"OPEN: {o:.2f} → NOW: {last:.2f}\n"
        f"Proč: {why or 'Bez jasné zprávy – sentiment/technika/trh.'}"
    )

def format_radar_report(rows: List[Dict[str, Any]], title: str, now: datetime) -> str:
    # režim trhu bereme z první řádky (všude stejné)
    regime = rows[0].get("regime") if rows else "—"
    regime_detail = rows[0].get("regime_detail") if rows else ""

    # TOP a WORST podle score
    rows_sorted = sorted(rows, key=lambda r: (r.get("score") or 0.0), reverse=True)
    top = rows_sorted[:TOP_N]
    worst = list(reversed(rows_sorted[-TOP_N:]))

    def block(label: str, items: List[Dict[str, Any]]) -> str:
        out = [label]
        for r in items:
            t = r["ticker"]
            p1d = r.get("pct_1d")
            sc = r.get("score")
            why = r.get("why", "")
            mv = r.get("movement", "")
            out.append(
                f"{_arrow(p1d)} {t} | 1D: {_fmt_pct(p1d)} {_bar(p1d)} | score: {sc:.2f} | {mv}\n"
                f"   why: {why}"
            )
            # max 2 news
            news = r.get("news") or []
            for src, nt, link in news[:2]:
                out.append(f"   • {src}: {nt}\n     {link}")
        return "\n".join(out)

    header = (
        f"📡 {title} ({now.strftime('%Y-%m-%d %H:%M')})\n"
        f"Režim trhu: {regime} | {regime_detail}\n"
    )

    return (
        header
        + "\n"
        + block("🔥 TOP kandidáti (dle score):", top)
        + "\n\n"
        + block("🧊 SLABÉ (dle score):", worst)
    )


# ============================================================
# ALERT DEDUPE (aby to nespamovalo)
# ============================================================
def alert_key(alert: Dict[str, Any]) -> str:
    # klíč = ticker + zaokrouhlený pct_from_open na 0.25% + movement
    p = float(alert.get("pct_from_open", 0.0))
    p_round = round(p / 0.25) * 0.25
    mv = str(alert.get("movement") or "")
    return f"{p_round:.2f}|{mv}"

def should_send_alert(ticker: str, key: str, day: str) -> bool:
    ded = read_json(ALERT_DEDUPE_FILE, {})
    cur = ded.get(ticker)
    if cur and cur.get("d") == day and cur.get("k") == key:
        return False
    ded[ticker] = {"d": day, "k": key}
    write_json(ALERT_DEDUPE_FILE, ded)
    return True


# ============================================================
# MAIN RUN
# ============================================================
def build_cfg_runtime() -> dict:
    """
    Kombinuje config.yml + runtime env.
    Engine si bere:
      - weights, benchmarks, portfolio/watchlist/new_candidates, ticker_map
    """
    cfg = CFG if isinstance(CFG, dict) else {}
    cfg = dict(cfg)
    cfg["runtime"] = {
        "news_per_ticker": NEWS_PER_TICKER,
        "alert_threshold": ALERT_THRESHOLD,
        "top_n": TOP_N,
    }
    return cfg

def run_premarket(cfg: dict, now: datetime):
    day = dt_to_date(now).isoformat()
    last_day = read_text(LAST_PREMARKET_DATE_FILE, "")
    if last_day == day:
        return

    rows = run_radar_snapshot(cfg, now, state=None)
    if not rows:
        telegram_send("⚠️ Premarket report: žádná data.")
        return

    msg = format_radar_report(rows, "MEGA INVESTIČNÍ RADAR – PREMARKET", now)
    telegram_send_long(msg)

    # Email 1× denně – pouze z premarket reportu
    last_email = read_text(LAST_EMAIL_DATE_FILE, "")
    if last_email != day:
        email_send(f"MEGA INVESTIČNÍ RADAR – PREMARKET ({day})", msg)
        write_text(LAST_EMAIL_DATE_FILE, day)

    write_text(LAST_PREMARKET_DATE_FILE, day)

def run_evening(cfg: dict, now: datetime):
    day = dt_to_date(now).isoformat()
    last_day = read_text(LAST_EVENING_DATE_FILE, "")
    if last_day == day:
        return

    rows = run_radar_snapshot(cfg, now, state=None)
    if not rows:
        telegram_send("⚠️ Večerní report: žádná data.")
        return

    msg = format_radar_report(rows, "MEGA INVESTIČNÍ RADAR – VEČER", now)
    telegram_send_long(msg)
    write_text(LAST_EVENING_DATE_FILE, day)

def run_alerts(cfg: dict, now: datetime):
    # alerty jen ve window (12–21)
    h = hm(now)
    if not in_window(h, ALERT_START, ALERT_END):
        return

    alerts = run_alerts_snapshot(cfg, now, state=None)
    if not alerts:
        return

    # pro hezčí "why" přidáme mini-why z posledních news z radar snapshotu (jen pro tickery co alertují)
    # (rychle: uděláme radar jen pro alert tickery, ať to není těžké)
    alert_tickers = [a["ticker"] for a in alerts]
    rows = run_radar_snapshot(cfg, now, state=None, universe=alert_tickers)
    why_map = {r["ticker"]: r.get("why") for r in rows}

    day = dt_to_date(now).isoformat()
    for a in sorted(alerts, key=lambda x: abs(float(x.get("pct_from_open", 0.0))), reverse=True):
        t = a["ticker"]
        k = alert_key(a)
        if not should_send_alert(t, k, day):
            continue
        msg = format_alert(a, why=why_map.get(t))
        telegram_send(msg)

def main():
    now = now_local()
    cfg = build_cfg_runtime()

    print(f"✅ Bot běží | RUN_MODE={RUN_MODE} | {now.strftime('%Y-%m-%d %H:%M')} ({TZ_NAME})")
    print(f"Reporty: {PREMARKET_TIME} & {EVENING_TIME} | Alerty: {ALERT_START}-{ALERT_END} (>= {ALERT_THRESHOLD}%)")

    # reporty spouštíme pouze přes „časové brány“, protože workflow běží každých 15 min
    if hm(now) == PREMARKET_TIME:
        run_premarket(cfg, now)
    if hm(now) == EVENING_TIME:
        run_evening(cfg, now)

    # alerty vždy v okně
    run_alerts(cfg, now)


if __name__ == "__main__":
    main()