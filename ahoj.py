import os
import json
import math
import requests
import feedparser
import yfinance as yf

from datetime import datetime, date
from zoneinfo import ZoneInfo

# YAML config (optional)
try:
    import yaml
except Exception:
    yaml = None


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

def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


# ============================================================
# ENV / SECRETS
# ============================================================
TELEGRAM_TOKEN = (os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
CHAT_ID = str(os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or "").strip()
FMP_API_KEY = (os.getenv("FMPAPIKEY") or os.getenv("FMP_API_KEY") or "").strip()

RUN_MODE = (os.getenv("RUN_MODE") or "run").strip().lower()  # run | backfill | learn (learn/backfill zatím jen držíme)

# Časy reportů (lokální čas Praha)
PREMARKET_TIME = os.getenv("PREMARKET_TIME", "12:00").strip()
EVENING_TIME = os.getenv("EVENING_TIME", "20:00").strip()

# Alert okno + práh (od dnešního OPEN)
ALERT_START = os.getenv("ALERT_START", "12:00").strip()
ALERT_END = os.getenv("ALERT_END", "21:00").strip()
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "3").strip())  # %

NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "2").strip())
TOP_N = int(os.getenv("TOP_N", "5").strip())

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ============================================================
# STATE (.state) - persist mezi běhy (GitHub cache)
# ============================================================
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

LAST_PREMARKET_DATE_FILE = os.path.join(STATE_DIR, "last_premarket_date.txt")
LAST_EVENING_DATE_FILE = os.path.join(STATE_DIR, "last_evening_date.txt")
LAST_ALERTS_FILE = os.path.join(STATE_DIR, "last_alerts.json")


# ============================================================
# CONFIG (optional config.yml / config.yaml)
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
        print("Telegram status:", r.status_code)
        if r.status_code != 200:
            print("Telegram odpověď:", r.text[:800])
    except Exception as e:
        print("Telegram error:", e)

def telegram_send_long(text: str):
    for part in chunk_text(text):
        telegram_send(part)


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
# TICKERS (z configu)
# ============================================================
def portfolio_from_cfg():
    items = cfg_get("portfolio", [])
    out = []
    if isinstance(items, list):
        for row in items:
            if isinstance(row, dict) and row.get("ticker"):
                out.append(str(row.get("ticker")).strip().upper())
    return out

PORTFOLIO = portfolio_from_cfg() or [
    "NVDA","TSM","MSFT","CVX","CSG","SGLD","NVO","NBIS","IREN","LEU"
]

WATCHLIST_CFG = cfg_get("watchlist", [])
WATCHLIST = []
if isinstance(WATCHLIST_CFG, list) and WATCHLIST_CFG:
    WATCHLIST = [str(x).strip().upper() for x in WATCHLIST_CFG if str(x).strip()]
else:
    WATCHLIST = ["SPY","QQQ","SMH"]

def new_candidates_from_cfg():
    raw = cfg_get("new_candidates", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raw = []
    out = [str(x).strip().upper() for x in raw]
    return [x for x in out if x]

NEW_CANDIDATES = new_candidates_from_cfg() or ["ASML","AMD","AVGO","CRWD","LLT"]

EXTRA_UNIVERSE = cfg_get("extra_universe", [])
if isinstance(EXTRA_UNIVERSE, list):
    EXTRA_UNIVERSE = [str(x).strip().upper() for x in EXTRA_UNIVERSE if str(x).strip()]
else:
    EXTRA_UNIVERSE = [
        "PLTR","AMZN","AAPL","GOOGL","META","TSLA","MSFT",
        "SMCI","ARM","MU","QCOM","ASML","AVGO","AMD","AMAT","LRCX","KLAC",
        "FCX","SCCO","RIO","BHP","AA","TECK","VALE","ALB",
        "GLD","SLV"
    ]

ALL_TICKERS = sorted(set(PORTFOLIO + WATCHLIST + NEW_CANDIDATES + EXTRA_UNIVERSE))


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

def volume_spike_yahoo(ticker: str):
    """Poměr dnešního objemu vs průměr 20 dní (1.0 = normál)."""
    try:
        h = yf.Ticker(ticker).history(period="2mo", interval="1d")
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

def daily_last_prev(ticker: str):
    """
    Vrátí (last_close, prev_close, src)
    Preferuje FMP, fallback Yahoo.
    """
    data = fmp_get("v3/historical-price-full/" + ticker, {"serietype": "line", "timeseries": 5})
    if isinstance(data, dict):
        hist = data.get("historical")
        if isinstance(hist, list) and len(hist) >= 2:
            c0 = safe_float(hist[0].get("close"))
            c1 = safe_float(hist[1].get("close"))
            if c0 is not None and c1 is not None:
                return c0, c1, "FMP"
    try:
        h = yf.Ticker(ticker).history(period="10d", interval="1d")
        if h is None or h.empty:
            return None, None, "—"
        closes = h["Close"].dropna()
        if len(closes) < 2:
            return None, None, "—"
        return float(closes.iloc[-1]), float(closes.iloc[-2]), "Yahoo"
    except Exception:
        return None, None, "—"

def intraday_open_last_yahoo(ticker: str):
    """Pro alerty: (open, last_close) z 5m dat za dnešek."""
    try:
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h is None or h.empty:
            return None
        o = safe_float(h["Open"].iloc[0])
        last = safe_float(h["Close"].iloc[-1])
        if o is None or last is None:
            return None
        return o, last
    except Exception:
        return None

def intraday_hilo_last_yahoo(ticker: str):
    """Pro klasifikaci: (high, low, last) z 5m dat za dnešek."""
    try:
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h is None or h.empty:
            return None
        hi = safe_float(h["High"].max())
        lo = safe_float(h["Low"].min())
        last = safe_float(h["Close"].iloc[-1])
        if hi is None or lo is None or last is None:
            return None
        return hi, lo, last
    except Exception:
        return None

def atr14_from_daily(ticker: str):
    """ATR(14) aproximace z denních dat."""
    try:
        h = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if h is None or h.empty:
            return None
        h = h.dropna()
        if len(h) < 20:
            return None
        high = h["High"]
        low = h["Low"]
        close = h["Close"]
        prev_close = close.shift(1)
        tr = (high - low).combine((high - prev_close).abs(), max).combine((low - prev_close).abs(), max)
        atr = tr.rolling(14).mean().iloc[-1]
        return safe_float(atr)
    except Exception:
        return None

def ret_5d_yahoo(ticker: str):
    try:
        h = yf.Ticker(ticker).history(period="8d", interval="1d")
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
# NEWS (FMP + RSS)
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
    # veřejné RSS pro symbol často funguje
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
# EARNINGS (FMP calendar)
# ============================================================
def fmp_next_earnings_date(ticker: str):
    data = fmp_get("v3/earning_calendar", {"symbol": ticker})
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
        except Exception:
            continue
        if d >= today:
            future.append(d)
    return min(future) if future else None

def days_to_earnings(ticker: str):
    ed = fmp_next_earnings_date(ticker)
    if not ed:
        return None
    return (ed - date.today()).days

def earnings_note(days_away):
    if days_away is None:
        return ""
    if days_away <= 2:
        return "⚠️ Earnings do 48h: vyšší riziko gapu."
    if days_away <= 7:
        return "⚠️ Earnings do týdne: vyšší volatilita."
    if days_away <= 14:
        return "ℹ️ Earnings do 2 týdnů."
    return ""


# ============================================================
# MARKET REGIME (SPY trend + VIX)
# ============================================================
def market_regime():
    label = "NEUTRÁLNÍ"
    detail = []
    try:
        spy = yf.Ticker("SPY").history(period="3mo", interval="1d")
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
# KLASIFIKACE POHYBU (NOVÝ PRO MODUL)
# ============================================================
def classify_move(ticker: str, pct1d, vol_ratio, atr14, day_high, day_low, news_items, days_earn):
    """
    Výstup: (label_emoji, label_text, detail_text)
    Heuristika swing/radar styl.
    """
    # fallbacky
    vol_ratio = vol_ratio if vol_ratio is not None else 1.0
    news_count = len(news_items) if news_items else 0

    day_range = None
    range_mult = None
    if day_high is not None and day_low is not None and atr14 is not None and atr14 > 0:
        day_range = day_high - day_low
        range_mult = day_range / atr14

    # event proximity
    earn_soon = (days_earn is not None and days_earn <= 2)

    # 1) Kapitulace / flush
    if pct1d is not None and abs(pct1d) >= 8 and vol_ratio >= 2.0 and (range_mult is None or range_mult >= 1.8):
        return "🟥", "KAPITULACE / FLUSH", f"Extrémní pohyb + vysoký objem ({vol_ratio:.2f}×) + rozšířený range."

    # 2) Událostní den (earnings/news driven)
    if earn_soon or (news_count >= 2 and (pct1d is not None and abs(pct1d) >= 4)) or (news_count >= 3):
        extra = []
        if earn_soon:
            extra.append("earnings do 48h")
        if news_count:
            extra.append(f"news={news_count}")
        if range_mult is not None:
            extra.append(f"range≈{range_mult:.2f}×ATR")
        return "🟧", "UDÁLOSTNÍ DEN", " | ".join(extra) if extra else "Pohyb řízen zprávami/katalyzátorem."

    # 3) Trendový den (directional expansion)
    if pct1d is not None and abs(pct1d) >= 2 and range_mult is not None and range_mult >= 1.3:
        direction = "bull" if pct1d > 0 else "bear"
        return "🟨", "TRENDOVÝ DEN", f"Směrový pohyb ({direction}) + rozšířený range≈{range_mult:.2f}×ATR."

    # 4) Normální den
    note = []
    if range_mult is not None:
        note.append(f"range≈{range_mult:.2f}×ATR")
    note.append(f"objem≈{vol_ratio:.2f}×")
    return "🟦", "NORMÁLNÍ DEN", " | ".join(note)


# ============================================================
# SCORE (jednoduché, konzervativní)
# ============================================================
def clamp(x, lo=0.0, hi=10.0):
    return max(lo, min(hi, x))

def score_from_signals(pct1d, rs5d, vol_ratio, news_items, days_earn, regime_label):
    """
    Konzervativní swing score 0..10.
    Neříká BUY/SELL, ale stav.
    """
    s = 0.0

    # momentum (abs 1D, ale tlumené)
    if pct1d is not None:
        s += clamp((abs(pct1d) / 6.0) * 3.0, 0.0, 3.0)

    # relative strength
    if rs5d is not None:
        # RS -5..+5 mapujeme na 0..3
        s += clamp(((rs5d + 5.0) / 10.0) * 3.0, 0.0, 3.0)

    # volume
    if vol_ratio is not None:
        s += clamp((vol_ratio - 1.0) * 1.5, 0.0, 2.0)

    # catalyst/news + earnings proximity
    n = len(news_items) if news_items else 0
    s += clamp(n * 0.4, 0.0, 1.2)
    if days_earn is not None:
        if days_earn <= 2:
            s += 1.5
        elif days_earn <= 7:
            s += 1.0
        elif days_earn <= 14:
            s += 0.5

    # market regime adjustment (konzervativní)
    if regime_label == "RISK-OFF":
        s -= 1.0
    elif regime_label == "RISK-ON":
        s += 0.3

    return clamp(s, 0.0, 10.0)

def suggestion_text(score, regime_label, days_earn):
    if days_earn is not None and days_earn <= 2:
        return "⚠️ Earnings do 48h: nehonit vstupy, vyšší gap risk."
    if regime_label == "RISK-OFF":
        if score >= 7.5:
            return "RISK-OFF: selektivně, spíš čekat na potvrzení/stabilizaci."
        if score <= 3.0:
            return "RISK-OFF: slabé – nedokupovat, zvážit redukci dle plánu."
        return "RISK-OFF: konzervativně, vyčkávat na jasnější edge."
    # risk-on / neutral
    if score >= 7.5:
        return "Silná konfluence – kandidát na swing setup (dle risku)."
    if score <= 3.0:
        return "Slabé – nízká pravděpodobnost edge, spíš monitoring."
    return "Neutrální – HOLD/monitoring, čekat na katalyzátor."

def fmt_pct(x):
    return "—" if x is None else f"{x:+.2f}%"


# ============================================================
# ALERTY (12-21, >=3% od dnešního OPEN)
# ============================================================
def load_last_alerts():
    d = read_json(LAST_ALERTS_FILE, {})
    if not isinstance(d, dict):
        d = {}
    # struktura: { "YYYY-MM-DD": { "TICKER": { "dir": "up/down", "sent": true } } }
    return d

def save_last_alerts(d):
    write_json(LAST_ALERTS_FILE, d)

def run_alerts(now_hm: str):
    if not in_window(now_hm, ALERT_START, ALERT_END):
        return

    if not is_weekday(now_local()):
        return

    last_alerts = load_last_alerts()
    tday = today_str()
    if tday not in last_alerts:
        last_alerts[tday] = {}

    for ticker in PORTFOLIO:
        got = intraday_open_last_yahoo(ticker)
        if not got:
            continue
        o, last = got
        ch = pct_change(last, o)
        if ch is None:
            continue
        if abs(ch) < ALERT_THRESHOLD:
            continue

        direction = "up" if ch > 0 else "down"
        prev = last_alerts[tday].get(ticker)

        # pošli jen jednou za den pro směr (aby to nespamovalo)
        if prev and prev.get("dir") == direction:
            continue

        msg = (
            f"🚨 ALERT {ticker}\n"
            f"Změna od OPEN: {fmt_pct(ch)} {bar(ch)}\n"
            f"OPEN: {o:.2f} | Aktuálně: {last:.2f}\n"
            f"Okno: {ALERT_START}–{ALERT_END} | práh: {ALERT_THRESHOLD:.1f}%"
        )
        telegram_send(msg)

        last_alerts[tday][ticker] = {"dir": direction, "sent_at": now_local().isoformat()}

    save_last_alerts(last_alerts)


# ============================================================
# REPORTY (12:00 a 20:00) – 1× denně
# ============================================================
def build_radar_report(kind: str):
    """
    kind: "PREMARKET" nebo "EVENING"
    """
    ts = now_local().strftime("%Y-%m-%d %H:%M")
    regime_label, regime_detail = market_regime()

    header = (
        f"📡 MEGA INVESTIČNÍ RADAR ({ts})\n"
        f"Režim trhu: {regime_label} | {regime_detail}\n"
        "────────────────────────────\n"
    )

    rows = []
    weak = []

    for ticker in ALL_TICKERS:
        last, prev, src = daily_last_prev(ticker)
        pct1d = pct_change(last, prev)

        rs5d = rel_strength_5d(ticker, bench="SPY")
        volr = volume_spike_yahoo(ticker)
        news_items = combined_news(ticker, NEWS_PER_TICKER)
        why = why_from_headlines(news_items)

        dte = days_to_earnings(ticker)
        enote = earnings_note(dte)

        hilo = intraday_hilo_last_yahoo(ticker)
        day_hi = day_lo = None
        if hilo:
            day_hi, day_lo, _ = hilo

        atr14 = atr14_from_daily(ticker)

        move_emoji, move_label, move_detail = classify_move(
            ticker=ticker,
            pct1d=pct1d,
            vol_ratio=volr,
            atr14=atr14,
            day_high=day_hi,
            day_low=day_lo,
            news_items=news_items,
            days_earn=dte
        )

        score = score_from_signals(pct1d, rs5d, volr, news_items, dte, regime_label)
        suggestion = suggestion_text(score, regime_label, dte)

        card = {
            "ticker": ticker,
            "pct1d": pct1d,
            "score": score,
            "rs5d": rs5d,
            "volr": volr,
            "src": src,
            "move": (move_emoji, move_label, move_detail),
            "why": why,
            "enote": enote,
            "news": news_items[:2],
        }
        rows.append(card)

        # slabé = nízké score + relevantní ticker (portfolio + new candidates + watchlist)
        if score <= 3.0 and ticker in set(PORTFOLIO + NEW_CANDIDATES + WATCHLIST):
            weak.append(card)

    # TOP kandidáti: nejvyšší score, ale filtrujeme, aby to bylo čitelné
    rows_sorted = sorted(rows, key=lambda x: x["score"], reverse=True)
    top = rows_sorted[:TOP_N]

    out = [header]

    out.append("🔥 TOP kandidáti (dle score):\n")
    for c in top:
        pct1d = c["pct1d"]
        move_emoji, move_label, move_detail = c["move"]

        out.append(
            f"{c['ticker']} | 1D: {fmt_pct(pct1d)} {bar(pct1d)}\n"
            f"{move_emoji} {move_label} ({move_detail})\n"
            f"score: {c['score']:.2f} | RS(5D-SPY): {fmt_pct(c['rs5d'])} | vol: {c['volr']:.2f}× | src:{c['src']}\n"
            f"→ {suggestion_text(c['score'], market_regime()[0], days_to_earnings(c['ticker']))}\n"
            f"why: {c['why']}\n"
        )
        if c["enote"]:
            out.append(f"{c['enote']}\n")

        for src, title, link in c["news"]:
            out.append(f"  • {src}: {title}\n    {link}\n")
        out.append("\n")

    if weak:
        out.append("🧊 SLABÉ (monitoring rizika):\n")
        for c in sorted(weak, key=lambda x: x["score"])[:TOP_N]:
            pct1d = c["pct1d"]
            move_emoji, move_label, move_detail = c["move"]
            out.append(
                f"{c['ticker']} | 1D: {fmt_pct(pct1d)} {bar(pct1d)}\n"
                f"{move_emoji} {move_label}\n"
                f"score: {c['score']:.2f} | src:{c['src']}\n"
                f"→ {suggestion_text(c['score'], market_regime()[0], days_to_earnings(c['ticker']))}\n"
                f"why: {c['why']}\n\n"
            )

    return "".join(out)

def maybe_send_report(now_hm: str):
    tday = today_str()

    # PREMARKET
    if now_hm >= PREMARKET_TIME:
        last = read_text(LAST_PREMARKET_DATE_FILE, "")
        if last != tday and is_weekday(now_local()):
            text = build_radar_report("PREMARKET")
            telegram_send_long(text)
            write_text(LAST_PREMARKET_DATE_FILE, tday)

    # EVENING
    if now_hm >= EVENING_TIME:
        last = read_text(LAST_EVENING_DATE_FILE, "")
        if last != tday and is_weekday(now_local()):
            text = build_radar_report("EVENING")
            telegram_send_long(text)
            write_text(LAST_EVENING_DATE_FILE, tday)


# ============================================================
# MAIN
# ============================================================
def main():
    now = now_local()
    now_hm = hm(now)

    print(f"✅ Radar běží | {now.isoformat()} | RUN_MODE={RUN_MODE}")
    print(f"   Portfolio: {len(PORTFOLIO)} | Universe: {len(ALL_TICKERS)}")
    print(f"   Reporty: {PREMARKET_TIME} & {EVENING_TIME} | Alerty: {ALERT_START}-{ALERT_END} (≥{ALERT_THRESHOLD}%)")

    # 1) Alerty (běží v okně)
    run_alerts(now_hm)

    # 2) Reporty (1× denně po dosažení času)
    maybe_send_report(now_hm)

    print("✅ Hotovo.")

if __name__ == "__main__":
    main()