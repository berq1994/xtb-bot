import os
import json
from datetime import datetime

import requests
import yfinance as yf
import feedparser

# ====== ČASOVÁ ZÓNA (Praha) ======
try:
    from zoneinfo import ZoneInfo
    CZ_TZ = ZoneInfo("Europe/Prague")
except Exception:
    CZ_TZ = None


def now_cz() -> datetime:
    return datetime.now(tz=CZ_TZ) if CZ_TZ else datetime.now()


def today_key() -> str:
    return now_cz().strftime("%Y-%m-%d")


# ====== SECRETS z GitHubu ======
TELEGRAMTOKEN = os.getenv("TELEGRAMTOKEN", "").strip()
CHATID = os.getenv("CHATID", "").strip()

# ====== PORTFOLIO (ticker symboly) ======
PORTFOLIO = [
    "CENX", "S", "NVO", "PYPL", "AMZN", "MSFT",
    "CVX", "NVDA", "TSM", "CAG", "META", "SNDK",
    "AAPL", "GOOGL", "TSLA",
    "PLTR", "SPY", "FCX", "IREN",
]

# ====== NASTAVENÍ ALERTŮ ======
ALERT_THRESHOLD_PCT = 5.0         # ±5 % od dnešního open
CHECK_ONLY_MARKET_HOURS = True    # mimo 15:30–22:05 CZ nic neposílá
INTRADAY_INTERVAL = "5m"          # stabilní; 1m bývá limitované

# ====== STATE (aby to nespamovalo) ======
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)
CROSS_STATE_FILE = os.path.join(STATE_DIR, "cross_state.json")


# ====== TELEGRAM ======
def tg_send(text: str) -> None:
    if not TELEGRAMTOKEN or not CHATID:
        print("Chybí TELEGRAMTOKEN nebo CHATID (GitHub Secrets).")
        return
    text = (text or "").strip()
    if not text:
        return

    url = f"https://api.telegram.org/bot{TELEGRAMTOKEN}/sendMessage"
    max_len = 3800
    for i in range(0, len(text), max_len):
        chunk = text[i:i + max_len]
        try:
            r = requests.post(url, data={"chat_id": CHATID, "text": chunk}, timeout=20)
            if r.status_code != 200:
                print("Telegram status:", r.status_code, r.text)
        except Exception as e:
            print("Telegram chyba:", e)


# ====== PŘEKLAD HEADLINE (pokud není knihovna, jede bez překladu) ======
try:
    from deep_translator import GoogleTranslator

    def translate_cs(s: str) -> str:
        try:
            return GoogleTranslator(source="auto", target="cs").translate(s)
        except Exception:
            return s
except Exception:
    def translate_cs(s: str) -> str:
        return s


# ====== MARKET HOURS (Praha) ======
def is_market_hours_prague() -> bool:
    """
    US regular session v Praze typicky 15:30–22:00.
    Dáváme rezervu do 22:05.
    """
    t = now_cz()
    if t.weekday() >= 5:  # So/Ne
        return False
    hhmm = t.strftime("%H:%M")
    return "15:30" <= hhmm <= "22:05"


# ====== STATE ======
def load_cross_state() -> dict:
    """
    Ukládá pro každý ticker a den poslední "stav":
    - IN: mezi -thr a +thr
    - UP: nad +thr
    - DOWN: pod -thr
    """
    if os.path.exists(CROSS_STATE_FILE):
        try:
            with open(CROSS_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cross_state(state: dict) -> None:
    with open(CROSS_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_state_key(ticker: str, day: str) -> str:
    return f"{ticker}:{day}"


# ====== DATA (yfinance) ======
def get_intraday_df(ticker: str):
    """
    Intraday data pro dnešek, regular session (prepost=False).
    """
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1d", interval=INTRADAY_INTERVAL, prepost=False)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def get_today_open_regular_session(ticker: str):
    df = get_intraday_df(ticker)
    if df is None:
        return None
    try:
        return float(df["Open"].dropna().iloc[0])
    except Exception:
        return None


def get_last_price_intraday(ticker: str):
    df = get_intraday_df(ticker)
    if df is None:
        return None
    try:
        return float(df["Close"].dropna().iloc[-1])
    except Exception:
        return None


def get_news_headline(ticker: str):
    try:
        feed = feedparser.parse(
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        )
        if not feed.entries:
            return None
        return feed.entries[0].title
    except Exception:
        return None


# ====== CROSSING LOGIKA ======
def classify_zone(change_pct: float, thr: float) -> str:
    """Vrátí IN / UP / DOWN podle změny od open."""
    if change_pct >= thr:
        return "UP"
    if change_pct <= -thr:
        return "DOWN"
    return "IN"


def check_alerts_crossing_from_open(tickers, threshold_pct: float = 5.0) -> None:
    """
    Alert jen při překročení hranice od open:
    - IN -> UP  (překročilo +thr)
    - IN -> DOWN (překročilo -thr)
    - DOWN -> IN -> DOWN (znovu překročí) => pošle znovu, protože se nejdřív vrátilo do IN
    - UP -> IN -> UP analogicky
    """
    state = load_cross_state()
    day = today_key()
    sent = 0

    for ticker in tickers:
        open_price = get_today_open_regular_session(ticker)
        last_price = get_last_price_intraday(ticker)

        if open_price is None or last_price is None or open_price == 0:
            continue

        change_pct = ((last_price - open_price) / open_price) * 100.0
        zone_now = classify_zone(change_pct, threshold_pct)

        key = get_state_key(ticker, day)
        zone_prev = state.get(key, "IN")  # default IN (na začátku dne)

        # Pokud se stav nezměnil, nic neposíláme
        if zone_now == zone_prev:
            continue

        # Uložíme nový stav vždy (aby fungoval crossing)
        state[key] = zone_now

        # Alert posíláme jen při přechodu do UP nebo DOWN
        if zone_now in ("UP", "DOWN"):
            emoji = "📈" if zone_now == "UP" else "📉"
            headline = get_news_headline(ticker)
            reason = f"\n📰 {translate_cs(headline)}" if headline else ""

            tg_send(
                f"⚠️ ALERT – překročení hranice od open ({day})\n"
                f"{emoji} {ticker}: {change_pct:+.2f} % od open\n"
                f"Open: {open_price:.2f} USD | Teď: {last_price:.2f} USD"
                f"{reason}"
            )
            sent += 1

    save_cross_state(state)
    print(f"Hotovo. Odesláno alertů: {sent}")


def main():
    if CHECK_ONLY_MARKET_HOURS and not is_market_hours_prague():
        print("Mimo obchodní hodiny (Praha). Končím.")
        return

    check_alerts_crossing_from_open(PORTFOLIO, threshold_pct=ALERT_THRESHOLD_PCT)


if __name__ == "__main__":
    main()
