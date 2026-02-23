import os
import json
import math
import time
import requests
import feedparser
import yfinance as yf
import matplotlib.pyplot as plt

from datetime import datetime, date
from zoneinfo import ZoneInfo

# YAML config (optional)
try:
    import yaml
except Exception:
    yaml = None

# Email (Gmail SMTP)
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


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
    return now_local().strftime("%Y-%m-%d")

def is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5

def to_minutes(hhmm: str) -> int:
    hh, mm = hhmm.split(":")
    return int(hh) * 60 + int(mm)

def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    n = to_minutes(now_hm)
    s = to_minutes(start_hm)
    e = to_minutes(end_hm)
    return s <= n <= e


# ============================================================
# STATE DIR
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

HISTORY_DIR = os.path.join(STATE_DIR, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_ALERTS_FILE = os.path.join(STATE_DIR, "last_alerts.json")
LEARNED_WEIGHTS_FILE = os.path.join(STATE_DIR, "learned_weights.json")
SNAPSHOTS_FILE = os.path.join(STATE_DIR, "snapshots.jsonl")


# ============================================================
# CONFIG (optional config.yml)
# ============================================================
DEFAULT_CONFIG_PATHS = ["config.yml", "config.yaml", ".github/config.yml", ".github/config.yaml"]

def load_cfg():
    if yaml is None:
        return {}
    path = None
    for p in DEFAULT_CONFIG_PATHS:
        if os.path.exists(p):
            path = p
            break
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

CFG = load_cfg()

def cfg_get(path, default=None):
    try:
        cur = CFG
        for part in path.split("."):
            if not isinstance(cur, dict):
                return default
            cur = cur.get(part)
        return default if cur is None else cur
    except Exception:
        return default


# ============================================================
# ENV (Secrets)
# ============================================================
TELEGRAM_TOKEN = (os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
CHAT_ID = str(os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or "").strip()
FMP_API_KEY = (os.getenv("FMPAPIKEY") or os.getenv("FMP_API_KEY") or "").strip()

RUN_MODE = (os.getenv("RUN_MODE") or "run").strip().lower()  # run | learn | backfill

PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()

ALERT_START = os.getenv("ALERT_START", "12:00").strip()
ALERT_END = os.getenv("ALERT_END", "21:00").strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3").strip())

NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2").strip())
TOP_N = int(os.getenv("TOP_N", "5").strip())

EMAIL_ENABLED = (os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true")
EMAIL_SENDER = (os.getenv("EMAIL_SENDER") or "").strip()
EMAIL_RECEIVER = (os.getenv("EMAIL_RECEIVER") or "").strip()
GMAILPASSWORD = (os.getenv("GMAILPASSWORD") or "").strip()

BACKFILL_START = os.getenv("BACKFILL_START", "2025-01-01").strip()
BACKFILL_END = os.getenv("BACKFILL_END", "").strip()

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ============================================================
# UTIL I/O
# ============================================================
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
# CZ TRANSLATION (news) – deep-translator optional
# ============================================================
def _translator():
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="auto", target="cs")
    except Exception:
        return None

_TRANSLATOR = _translator()
_TRANSLATE_CACHE = {}

def cz(text: str) -> str:
    if not text:
        return ""
    key = text.strip()
    if len(key) < 5:
        return key
    if key in _TRANSLATE_CACHE:
        return _TRANATE_CACHE[key]
    if _TRANSLATOR is None:
        _TRANSLATE_CACHE[key] = key
        return key
    try:
        out = _TRANSLATOR.translate(key)
        _TRANSLATE_CACHE[key] = out
        return out
    except Exception:
        _TRANSLATE_CACHE[key] = key
        return key


# ============================================================
# TELEGRAM
# ============================================================
def chunk_text(text: str, limit: int = 3500):
    parts, buf = [], ""
    for line in text.splitlines(True):
        if len(buf) + len(line) > limit:
            parts.append(buf)
            buf = ""
        buf += line
    if buf.strip():
        parts.append(buf)
    return parts

def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram není nastaven: chybí token/chat_id.")
        return
    try:
        r = requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=35
        )
        if r.status_code != 200:
            print("Telegram odpověď:", r.text[:500])
    except Exception as e:
        print("Telegram error:", e)

def telegram_send_long(text: str):
    for part in chunk_text(text):
        telegram_send(part)


# ============================================================
# EMAIL (Gmail SMTP)
# ============================================================
def email_send(subject: str, body_text: str, image_paths=None):
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

    image_paths = image_paths or []
    for path in image_paths:
        try:
            with open(path, "rb") as f:
                img = MIMEImage(f.read())
            img.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
            msg.attach(img)
        except Exception as e:
            print("⚠️ Příloha obrázku chyba:", path, e)

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
# FMP API (optional)
# ============================================================
def fmp_get(path: str, params=None):
    key = (FMP_API_KEY or cfg_get("fmp_api_key", "") or "").strip()
    if not key:
        return None
    url = f"https://financialmodelingprep.com/api/{path}"
    p = dict(params or {})
    p["apikey"] = key
    try:
        r = requests.get(url, params=p, timeout=25)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


# ============================================================
# TICKERS + MAP
# ============================================================
def _as_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return []

def portfolio_from_cfg():
    items = cfg_get("portfolio", [])
    out = []
    for row in _as_list(items):
        if isinstance(row, dict) and row.get("ticker"):
            out.append(str(row.get("ticker")).strip().upper())
    return out

PORTFOLIO = portfolio_from_cfg() or ["NVDA","TSM","MSFT","CVX","CSG","SGLD","NVO","NBIS","IREN","LEU"]
WATCHLIST = [str(x).strip().upper() for x in _as_list(cfg_get("watchlist", ["SPY","QQQ","SMH"])) if str(x).strip()]
NEW_CANDIDATES = [str(x).strip().upper() for x in _as_list(cfg_get("new_candidates", [])) if str(x).strip()] or ["ASML","AMD","AVGO","CRWD","LLT"]
EXTRA_UNIVERSE = [str(x).strip().upper() for x in _as_list(cfg_get("extra_universe", [])) if str(x).strip()] or ["SPY","QQQ","SMH"]

ALL_TICKERS = sorted(set(PORTFOLIO + WATCHLIST + NEW_CANDIDATES + EXTRA_UNIVERSE))

TICKER_MAP = cfg_get("ticker_map", {})
if not isinstance(TICKER_MAP, dict):
    TICKER_MAP = {}

def sym(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    mapped = TICKER_MAP.get(t)
    return str(mapped).strip() if mapped else t


# ============================================================
# DATA HELPERS
# ============================================================
def safe_float(x):
    try:
        if x is None:
            return None
        x = float(x)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None

def pct_change(new, old):
    if new is None or old is None or old == 0:
        return None
    return ((new - old) / old) * 100.0

def bar(pct: float, width: int = 14) -> str:
    if pct is None:
        return ""
    a = min(abs(pct), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)

def daily_last_prev(ticker: str):
    # FMP
    data = fmp_get("v3/historical-price-full/" + ticker, {"serietype": "line", "timeseries": 5})
    if isinstance(data, dict):
        hist = data.get("historical")
        if isinstance(hist, list) and len(hist) >= 2:
            c0 = safe_float(hist[0].get("close"))
            c1 = safe_float(hist[1].get("close"))
            if c0 is not None and c1 is not None:
                return c0, c1, "FMP"

    # Yahoo fallback
    ysym = sym(ticker)
    try:
        h = yf.Ticker(ysym).history(period="10d", interval="1d")
        if h is None or h.empty:
            return None, None, "—"
        closes = h["Close"].dropna()
        if len(closes) < 2:
            return None, None, "—"
        return float(closes.iloc[-1]), float(closes.iloc[-2]), "Yahoo"
    except Exception:
        return None, None, "—"

def intraday_open_last_yahoo(ticker: str):
    ysym = sym(ticker)
    try:
        h = yf.Ticker(ysym).history(period="1d", interval="5m")
        if h is None or h.empty:
            return None
        o = safe_float(h["Open"].iloc[0])
        last = safe_float(h["Close"].iloc[-1])
        if o is None or last is None:
            return None
        return o, last
    except Exception:
        return None

def volume_spike_yahoo(ticker: str):
    ysym = sym(ticker)
    try:
        h = yf.Ticker(ysym).history(period="2mo", interval="1d")
        if h is None or h.empty or "Volume" not in h:
            return 1.0
        v = h["Volume"].dropna()
        if len(v) < 10:
            return 1.0
        avg20 = float(v.tail(20).mean())
        lastv = float(v.iloc[-1])
        if avg20 <= 0:
            return 1.0
        return lastv / avg20
    except Exception:
        return 1.0

def ret_5d_yahoo(ticker: str):
    ysym = sym(ticker)
    try:
        h = yf.Ticker(ysym).history(period="8d", interval="1d")
        if h is None or h.empty:
            return None
        c = h["Close"].dropna()
        if len(c) < 6:
            return None
        return (float(c.iloc[-1]) - float(c.iloc[-6])) / float(c.iloc[-6]) * 100.0
    except Exception:
        return None

def rel_strength_5d(ticker: str, bench="SPY"):
    r_t = ret_5d_yahoo(ticker)
    r_b = ret_5d_yahoo(bench)
    if r_t is None or r_b is None:
        return None
    return r_t - r_b


# ============================================================
# NEWS
# ============================================================
def rss_entries(url: str, limit: int):
    feed = feedparser.parse(url)
    out = []
    for e in (feed.entries or [])[:limit]:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        if title:
            out.append((title, link))
    return out

def news_fmp(ticker: str, limit: int):
    data = fmp_get("v3/stock_news", {"tickers": ticker, "limit": limit})
    if not isinstance(data, list):
        return []
    out = []
    for row in data[:limit]:
        title = (row.get("title") or "").strip()
        link = (row.get("url") or "").strip()
        if title:
            out.append(("FMP", title, link))
    return out

def news_yahoo_rss(ticker: str, limit: int):
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    return [("Yahoo", t, l) for t, l in rss_entries(url, limit)]

def news_seekingalpha_rss(ticker: str, limit: int):
    url = f"https://seekingalpha.com/symbol/{ticker}.xml"
    return [("SeekingAlpha", t, l) for t, l in rss_entries(url, limit)]

def news_google_rss(ticker: str, limit: int):
    q = requests.utils.quote(f"{ticker} stock OR {ticker} earnings OR {ticker} guidance")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return [("GoogleNews", t, l) for t, l in rss_entries(url, limit)]

def combined_news(ticker: str, limit_each: int):
    items = []
    items += news_fmp(ticker, limit_each)
    items += news_yahoo_rss(ticker, limit_each)
    items += news_seekingalpha_rss(ticker, limit_each)
    items += news_google_rss(ticker, limit_each)

    seen = set()
    uniq = []
    for src, title, link in items:
        key = title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((src, title, link))
    return uniq

WHY_KEYWORDS = [
    (["earnings", "results", "quarter", "beat", "miss"], "výsledky (earnings) / překvapení vs očekávání"),
    (["guidance", "outlook", "forecast", "raises", "cuts"], "výhled (guidance) / změna očekávání"),
    (["upgrade", "downgrade", "price target", "rating"], "analytické doporučení (upgrade/downgrade/cílová cena)"),
    (["acquire", "acquisition", "merger", "deal"], "akvizice / fúze / transakce"),
    (["sec", "investigation", "lawsuit", "regulator", "antitrust"], "regulace / vyšetřování / právní zprávy"),
    (["contract", "partnership", "orders"], "zakázky / partnerství / objednávky"),
    (["chip", "ai", "gpu", "data center", "semiconductor"], "AI/čipy – sektorové zprávy"),
    (["dividend", "buyback", "repurchase"], "dividenda / buyback"),
]

def why_from_headlines(news_items):
    if not news_items:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    titles = " ".join([t for (_, t, _) in news_items]).lower()
    hits = []
    for keys, reason in WHY_KEYWORDS:
        if any(k in titles for k in keys):
            hits.append(reason)
    if not hits:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    return "; ".join(hits[:2]) + "."


# ============================================================
# MARKET REGIME
# ============================================================
def market_regime():
    label = "NEUTRÁLNÍ"
    detail = []
    try:
        spy = yf.Ticker(sym("SPY")).history(period="3mo", interval="1d")
        if spy is not None and not spy.empty:
            close = spy["Close"].dropna()
            if len(close) >= 25:
                c0 = float(close.iloc[-1])
                ma20 = float(close.tail(20).mean())
                trend = (c0 - ma20) / ma20 * 100.0
                detail.append(f"SPY vs MA20: {trend:+.2f}%")
                if trend > 0.7:
                    label = "RISK-ON"
                elif trend < -0.7:
                    label = "RISK-OFF"

        vix = yf.Ticker("^VIX").history(period="1mo", interval="1d")
        if vix is not None and not vix.empty:
            v = vix["Close"].dropna()
            if len(v) >= 6:
                v_now = float(v.iloc[-1])
                v_5 = float(v.iloc[-6])
                v_ch = (v_now - v_5) / v_5 * 100.0
                detail.append(f"VIX 5D: {v_ch:+.1f}% (aktuálně {v_now:.1f})")
                if v_ch > 10:
                    label = "RISK-OFF"
                elif v_ch < -10 and label != "RISK-OFF":
                    label = "RISK-ON"
    except Exception:
        pass
    return label, "; ".join(detail) if detail else "Bez dostatečných dat."


# ============================================================
# WEIGHTS + SCORE
# ============================================================
DEFAULT_WEIGHTS = {
    "momentum": float(cfg_get("weights.momentum", 0.25)),
    "rel_strength": float(cfg_get("weights.rel_strength", 0.20)),
    "volatility_volume": float(cfg_get("weights.volatility_volume", 0.15)),
    "catalyst": float(cfg_get("weights.catalyst", 0.20)),
    "market_regime": float(cfg_get("weights.market_regime", 0.20)),
}

def load_weights():
    w = dict(DEFAULT_WEIGHTS)
    learned = read_json(LEARNED_WEIGHTS_FILE, {})
    if isinstance(learned, dict):
        for k in w:
            if k in learned and isinstance(learned[k], (int, float)):
                w[k] = float(learned[k])
    s = sum(w.values())
    if s > 0:
        for k in w:
            w[k] = w[k] / s
    return w

def clamp(x, lo=0.0, hi=10.0):
    return max(lo, min(hi, x))

def momentum_score_1d(pct1d):
    if pct1d is None:
        return 0.0
    return clamp((abs(pct1d) / 8.0) * 10.0, 0.0, 10.0)

def rs_score(rs):
    if rs is None:
        return 0.0
    return clamp(rs + 5.0, 0.0, 10.0)

def vol_score(vol_ratio):
    if vol_ratio is None:
        return 0.0
    return clamp((vol_ratio - 1.0) * 6.0, 0.0, 10.0)

def catalyst_score(news_items):
    if not news_items:
        return 0.0
    return clamp(min(10.0, 1.0 + 0.9 * len(news_items)), 0.0, 10.0)

def regime_score(regime_label):
    return 10.0 if regime_label == "RISK-ON" else (0.0 if regime_label == "RISK-OFF" else 5.0)

def total_score(weights, mom, rs, vol, cat, reg):
    return (
        weights["momentum"] * mom +
        weights["rel_strength"] * rs +
        weights["volatility_volume"] * vol +
        weights["catalyst"] * cat +
        weights["market_regime"] * reg
    )

def action_suggestion(score, regime_label):
    if regime_label == "RISK-OFF":
        if score >= 7.8:
            return "SILNÉ, ale RISK-OFF: spíš čekat / menší pozice."
        if score <= 3.2:
            return "SLABÉ + RISK-OFF: zvážit redukci / nedokupovat."
        return "RISK-OFF: konzervativně."
    if score >= 7.8:
        return "KANDIDÁT NA PŘIKOUPENÍ / VSTUP (dle rizika)."
    if score <= 3.2:
        return "KANDIDÁT NA REDUKCI / PRODEJ (pokud sedí do plánu)."
    return "NEUTRÁL: HOLD."

def format_line(ticker, pct1d, score, suggestion, why, rs, vol_ratio, src):
    pct_txt = "—" if pct1d is None else f"{pct1d:+.2f}% {bar(pct1d)}"
    rs_txt = "—" if rs is None else f"{rs:+.2f}"
    vol_txt = f"{vol_ratio:.2f}×" if isinstance(vol_ratio, (int, float)) else "—"
    return (
        f"{ticker} | 1D: {pct_txt}\n"
        f"score: {score:.2f} | RS(5D-SPY): {rs_txt} | vol: {vol_txt} | src:{src}\n"
        f"→ {suggestion}\n"
        f"why: {why}\n"
    )

def append_snapshot(obj: dict):
    try:
        with open(SNAPSHOTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass

def plot_price_chart(ticker: str, days: int = 180) -> str:
    ysym = sym(ticker)
    try:
        h = yf.Ticker(ysym).history(period=f"{days}d", interval="1d")
        if h is None or h.empty:
            return ""
        close = h["Close"].dropna()
        if len(close) < 10:
            return ""
        path = os.path.join(STATE_DIR, f"chart_{ticker}.png")
        plt.figure()
        plt.plot(close.index, close.values)
        plt.title(f"{ticker} ({ysym}) - {days}d")
        plt.xlabel("Datum")
        plt.ylabel("Cena")
        plt.tight_layout()
        plt.savefig(path, dpi=150)
        plt.close()
        return path
    except Exception:
        return ""


# ============================================================
# ALERTS
# ============================================================
def load_last_alerts():
    data = read_json(LAST_ALERTS_FILE, {})
    return data if isinstance(data, dict) else {}

def save_last_alerts(data: dict):
    write_json(LAST_ALERTS_FILE, data)

def run_alerts():
    now = now_local()
    if not in_window(hm(now), ALERT_START, ALERT_END):
        return

    last_alerts = load_last_alerts()
    today = today_str()
    out_lines = []

    for t in PORTFOLIO:
        intr = intraday_open_last_yahoo(t)
        if not intr:
            continue
        o, last = intr
        ch = pct_change(last, o)
        if ch is None or abs(ch) < ALERT_THRESHOLD:
            continue

        direction = "up" if ch > 0 else "down"
        prev = last_alerts.get(t, {})
        if isinstance(prev, dict) and prev.get("date") == today and prev.get("dir") == direction:
            continue

        out_lines.append(f"🚨 ALERT {t}: {ch:+.2f}% od OPEN (open={o:.2f}, now={last:.2f})")
        last_alerts[t] = {"date": today, "dir": direction, "pct": ch, "ts": now.isoformat()}

    if out_lines:
        telegram_send_long("\n".join(out_lines))

    save_last_alerts(last_alerts)


# ============================================================
# REPORT
# ============================================================
def build_radar_report():
    weights = load_weights()
    regime_label, regime_detail = market_regime()

    lines = []
    lines.append(f"📡 MEGA INVESTIČNÍ RADAR ({today_str()} {hm(now_local())})")
    lines.append(f"Režim trhu: {regime_label} | {regime_detail}")
    lines.append("")

    rows = []
    for t in ALL_TICKERS:
        last, prev, src = daily_last_prev(t)
        pct1d = pct_change(last, prev)
        rs = rel_strength_5d(t, bench=cfg_get("benchmarks.spy", "SPY"))
        volr = volume_spike_yahoo(t)
        news = combined_news(t, NEWS_PER_TICKER)
        why = why_from_headlines(news)

        mom = momentum_score_1d(pct1d)
        rs_s = rs_score(rs)
        vol_s = vol_score(volr)
        cat_s = catalyst_score(news)
        reg_s = regime_score(regime_label)

        score = total_score(weights, mom, rs_s, vol_s, cat_s, reg_s)
        suggestion = action_suggestion(score, regime_label)

        rows.append({
            "ticker": t,
            "pct1d": pct1d,
            "score": score,
            "suggestion": suggestion,
            "why": why,
            "rs": rs,
            "volr": volr,
            "src": src,
            "news": news[:NEWS_PER_TICKER]
        })

    sorted_by_score = sorted(rows, key=lambda x: x["score"], reverse=True)
    top = sorted_by_score[:TOP_N]
    bottom = list(reversed(sorted_by_score[-TOP_N:]))

    lines.append("🔥 TOP kandidáti (dle score):")
    for r in top:
        lines.append(format_line(r["ticker"], r["pct1d"], r["score"], r["suggestion"], r["why"], r["rs"], r["volr"], r["src"]))
        for (src, title, link) in r["news"]:
            lines.append(f"  • {src}: {title}")
            lines.append(f"    {link}")
        lines.append("")

    lines.append("🧊 SLABÉ (kandidáti na redukci):")
    for r in bottom:
        lines.append(format_line(r["ticker"], r["pct1d"], r["score"], r["suggestion"], r["why"], r["rs"], r["volr"], r["src"]))
        lines.append("")

    report = "\n".join(lines)

    append_snapshot({"ts": now_local().isoformat(), "top": top, "bottom": bottom})
    return report, top, bottom


def send_reports_if_time():
    now = now_local()
    t = hm(now)
    today = today_str()

    report, top, _ = build_radar_report()

    last_pre = read_text(LAST_PREMARKET_DATE_FILE, "")
    if to_minutes(t) >= to_minutes(PREMARKET_TIME) and last_pre != today:
        telegram_send_long(report)

        img_paths = []
        for r in top[:3]:
            p = plot_price_chart(r["ticker"], 180)
            if p:
                img_paths.append(p)

        email_send(
            subject=f"MEGA INVESTIČNÍ RADAR – {today} {t}",
            body_text=report,
            image_paths=img_paths
        )
        write_text(LAST_PREMARKET_DATE_FILE, today)
        return  # pokud už poslal premarket, v tom samém runu už neposílej evening

    last_eve = read_text(LAST_EVENING_DATE_FILE, "")
    if to_minutes(t) >= to_minutes(EVENING_TIME) and last_eve != today:
        telegram_send_long(report)
        email_send(
            subject=f"MEGA INVESTIČNÍ RADAR (večer) – {today} {t}",
            body_text=report,
            image_paths=[]
        )
        write_text(LAST_EVENING_DATE_FILE, today)


# ============================================================
# ENTRYPOINT
# ============================================================
def main():
    now = now_local()
    print(f"✅ Bot start | mode={RUN_MODE} | tz={TZ_NAME} | now={now.isoformat()} | tickers={len(ALL_TICKERS)}")
    print(f"Secrets check: TG_TOKEN:{bool(TELEGRAM_TOKEN)} CHAT_ID:{bool(CHAT_ID)} FMP:{bool(FMP_API_KEY)} "
          f"EMAIL_ENABLED:{EMAIL_ENABLED} EMAIL_SENDER:{bool(EMAIL_SENDER)} EMAIL_RECEIVER:{bool(EMAIL_RECEIVER)}")

    if RUN_MODE == "run":
        run_alerts()
        send_reports_if_time()
        print("✅ Done.")
        return

    print("ℹ️ Tento build řeší hlavně RUN režim (reporty + alerty).")


if __name__ == "__main__":
    main()