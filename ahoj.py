import os
import json
import time
import math
import pytz
import requests
import feedparser
import yfinance as yf
from datetime import datetime, date
from deep_translator import GoogleTranslator

# =========================================================
# PRO XTB BOT (GitHub Actions friendly)
# - Alerty jen 15:30–21:00 Europe/Prague
# - Alert jen při změně od dnešního OPEN >= ±5%
# - Denní report max 1× denně (Telegram + volitelně email v budoucnu)
# - Lepší formát zpráv + celé názvy firem + krátký popis
# - Stav se ukládá do .state/ (cache v Actions)
# =========================================================

# ====== ENV (GitHub Secrets) ======
TELEGRAM_TOKEN = os.getenv("TELEGRAMTOKEN", "").strip()
CHAT_ID = str(os.getenv("CHATID", "")).strip()
FMP_API_KEY = os.getenv("FMPAPIKEY", "").strip()

# ====== Nastavení ======
TIMEZONE = os.getenv("TIMEZONE", "Europe/Prague").strip()
ALERT_START = os.getenv("ALERT_START", "15:30").strip()  # Praha
ALERT_END = os.getenv("ALERT_END", "21:00").strip()      # Praha
REPORT_TIME = os.getenv("REPORT_TIME", "15:30").strip()  # Praha

ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "5"))  # v %

# Portfolio lze přepsat env proměnnou PORTFOLIO="AAPL,MSFT,..."
PORTFOLIO_ENV = os.getenv("PORTFOLIO", "").strip()

DEFAULT_PORTFOLIO = [
    "CENX","S","NVO","PYPL","AMZN","MSFT","CVX","NVDA","TSM","CAG","META","AAPL","GOOGL","TSLA",
    "PLTR","SPY","FCX","IREN"
]

PORTFOLIO = [t.strip().upper() for t in PORTFOLIO_ENV.split(",") if t.strip()] if PORTFOLIO_ENV else DEFAULT_PORTFOLIO

# ====== Firma -> celé jméno + krátce co dělá ======
COMPANY_INFO = {
    "CENX": ("Century Aluminum Company", "Hliník (výroba/produkce). Citlivé na cenu energie a průmyslovou poptávku."),
    "S": ("SentinelOne, Inc.", "Kyberbezpečnost (endpoint/cloud). Růstový sektor, vyšší volatilita."),
    "NVO": ("Novo Nordisk A/S", "Farmacie (diabetes/obezita). Defenzivnější růstový titul."),
    "PYPL": ("PayPal Holdings, Inc.", "Platby/fintech. Citlivé na spotřebu a konkurenci."),
    "AMZN": ("Amazon.com, Inc.", "E-commerce + AWS cloud. Mix růstu a cashflow."),
    "MSFT": ("Microsoft Corporation", "Software + cloud + AI. Jedna z hlavních AI platforem."),
    "CVX": ("Chevron Corporation", "Ropa a plyn. Citlivé na cenu ropy, často dividendové."),
    "NVDA": ("NVIDIA Corporation", "GPU/AI čipy. Vysoký růst + volatilita."),
    "TSM": ("Taiwan Semiconductor Manufacturing Co.", "Největší foundry. Klíčové pro čipy a AI."),
    "CAG": ("Conagra Brands, Inc.", "Potraviny (defenziva). Stabilnější, menší volatilita."),
    "META": ("Meta Platforms, Inc.", "Sociální sítě + reklama + AI. Cyklus reklamy."),
    "AAPL": ("Apple Inc.", "Hardware + služby. Silná značka, stabilnější."),
    "GOOGL": ("Alphabet Inc.", "Vyhledávání + reklama + cloud + AI. Silná AI infrastruktura."),
    "TSLA": ("Tesla, Inc.", "EV + energy. Velká volatilita, citlivé na sentiment."),
    "PLTR": ("Palantir Technologies Inc.", "Data/AI platformy pro firmy a stát. Volatilní růstovka."),
    "SPY": ("SPDR S&P 500 ETF Trust", "ETF na S&P 500. Široká diverzifikace USA trhu."),
    "FCX": ("Freeport-McMoRan Inc.", "Měď. Téma elektrifikace/AI infrastruktury."),
    "IREN": ("Iris Energy Limited", "Datacentra/AI + energetika. Vyšší riziko/volatilita."),
}

# ====== Stav ======
STATE_DIR = ".state"
os.makedirs(STATE_DIR, exist_ok=True)

STATE_FILE = os.path.join(STATE_DIR, "state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

STATE = load_state()

# ====== Pomocné ======
def now_local():
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)

def hm_to_minutes(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)

def in_alert_window(dt: datetime) -> bool:
    cur = dt.hour * 60 + dt.minute
    return hm_to_minutes(ALERT_START) <= cur <= hm_to_minutes(ALERT_END)

def is_report_time(dt: datetime) -> bool:
    # tolerujeme okno 15 minut (Actions běží po 15 min)
    target = hm_to_minutes(REPORT_TIME)
    cur = dt.hour * 60 + dt.minute
    return abs(cur - target) <= 7  # +-7 minut

def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Chybí TELEGRAMTOKEN nebo CHATID.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    r = requests.post(url, data=payload, timeout=30)
    print("Telegram status:", r.status_code)
    if r.status_code != 200:
        print("Telegram odpověď:", r.text)
        return False
    return True

def translate_to_cs(text: str) -> str:
    try:
        return GoogleTranslator(source="auto", target="cs").translate(text)
    except:
        return text

# ====== Data (cena + open) ======
def get_open_and_last(ticker: str):
    """
    Vrací (open_today, last_price).
    Používá denní data. Pokud dnešní řádek chybí (svátek), vrátí (None, None).
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d")
        if hist is None or hist.empty:
            return None, None

        # vezmeme poslední dostupný den (většinou dnešek nebo včerejšek)
        last_row = hist.iloc[-1]
        open_price = float(last_row["Open"]) if not math.isnan(float(last_row["Open"])) else None
        last_price = float(last_row["Close"]) if not math.isnan(float(last_row["Close"])) else None

        # zkusíme fast_info last_price (čerstvější), když jde
        try:
            fi = t.fast_info
            lp = fi.get("last_price", None)
            if lp is not None:
                last_price = float(lp)
        except:
            pass

        return open_price, last_price
    except Exception as e:
        print(f"{ticker}: chyba při cenách: {e}")
        return None, None

# ====== Novinky (Yahoo RSS -> přeložit titulky) ======
def get_top_news_lines(ticker: str, limit: int = 2):
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        feed = feedparser.parse(url)
        entries = feed.entries[:limit] if feed and feed.entries else []
        lines = []
        for e in entries:
            title = translate_to_cs(getattr(e, "title", "").strip())
            if title:
                lines.append(f"• {title}")
        return lines
    except:
        return []

# ====== Earnings (primárně FMP, fallback yfinance) ======
def fmp_income_quarter(ticker: str):
    """
    Vrátí (date_str, net_income, revenue) nebo (None, None, None)
    """
    if not FMP_API_KEY:
        return None, None, None
    try:
        url = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}?period=quarter&limit=1&apikey={FMP_API_KEY}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return None, None, None
        data = r.json()
        if not isinstance(data, list) or not data:
            return None, None, None
        row = data[0]
        d = row.get("date")
        net = row.get("netIncome")
        rev = row.get("revenue")
        return d, net, rev
    except:
        return None, None, None

def yfin_income_quarter(ticker: str):
    """
    Fallback: zkusí yfinance financials (může být prázdné)
    """
    try:
        t = yf.Ticker(ticker)
        fin = t.quarterly_financials
        if fin is None or fin.empty:
            return None, None, None
        # poslední sloupec je nejnovější kvartál
        col = fin.columns[0]
        net = fin.loc["Net Income", col] if "Net Income" in fin.index else None
        rev = fin.loc["Total Revenue", col] if "Total Revenue" in fin.index else None
        d = str(col.date()) if hasattr(col, "date") else str(col)
        return d, None if net is None else float(net), None if rev is None else float(rev)
    except:
        return None, None, None

def get_earnings(ticker: str):
    d, net, rev = fmp_income_quarter(ticker)
    if d is not None and (net is not None or rev is not None):
        return d, net, rev

    d2, net2, rev2 = yfin_income_quarter(ticker)
    return d2, net2, rev2

# ====== Formátování ======
def fmt_money(x):
    if x is None:
        return "—"
    try:
        x = float(x)
        if abs(x) >= 1e9:
            return f"{x/1e9:.2f}B"
        if abs(x) >= 1e6:
            return f"{x/1e6:.2f}M"
        return f"{x:,.0f}".replace(",", " ")
    except:
        return "—"

def company_line(ticker: str):
    name, desc = COMPANY_INFO.get(ticker, (ticker, ""))
    return f"{ticker} — {name}\n{desc}".strip()

# ====== Alerty ======
def send_alert(ticker: str, open_p: float, last_p: float, change_pct: float, ts: datetime):
    direction = "📈" if change_pct > 0 else "📉"
    name = COMPANY_INFO.get(ticker, (ticker, ""))[0]

    msg = (
        f"🚨 *ALERT {direction}*\n"
        f"{ticker} — {name}\n"
        f"Změna od OPEN: {change_pct:+.2f}%\n"
        f"OPEN: {open_p:.2f}  →  NOW: {last_p:.2f}\n"
        f"Čas: {ts.strftime('%d.%m.%Y %H:%M')} ({TIMEZONE})"
    )
    # Telegram bez markdown režimu kvůli jednoduchosti
    msg = msg.replace("*", "")
    send_telegram(msg)

# ====== Denní report ======
def send_daily_report(ts: datetime):
    today = ts.strftime("%Y-%m-%d")
    last_sent = STATE.get("last_daily_report_date")
    if last_sent == today:
        print("Denní report už dnes byl odeslán.")
        return

    lines = []
    lines.append(f"📊 DENNÍ REPORT — {ts.strftime('%d.%m.%Y %H:%M')} ({TIMEZONE})")
    lines.append("")

    sent_any = False

    for ticker in PORTFOLIO:
        open_p, last_p = get_open_and_last(ticker)
        if open_p is None or last_p is None:
            lines.append(f"{ticker}: data nejsou dostupná.")
            lines.append("")
            continue

        change_pct = ((last_p - open_p) / open_p) * 100 if open_p else 0.0

        name, desc = COMPANY_INFO.get(ticker, (ticker, ""))
        lines.append(f"✅ {ticker} — {name}")
        lines.append(f"Cena: {last_p:.2f} | od OPEN: {change_pct:+.2f}%")
        if desc:
            lines.append(f"Co dělá: {desc}")

        news = get_top_news_lines(ticker, limit=2)
        if news:
            lines.append("Novinky:")
            lines.extend(news)

        d, net, rev = get_earnings(ticker)
        if d:
            # Net income/revenue můžou být None — nevypisujeme NaN
            ni = fmt_money(net) if net is not None else "—"
            rv = fmt_money(rev) if rev is not None else "—"
            lines.append(f"Earnings (kvartál {d}): Net income={ni}, Revenue={rv}")

        lines.append("")  # mezera mezi firmami
        sent_any = True

    if not sent_any:
        send_telegram("⚠️ Denní report: žádná data.")
        return

    # Telegram limit zprávy — pro jistotu pošleme po blocích
    chunk = []
    total = 0
    for line in lines:
        add = (line + "\n")
        if total + len(add) > 3500:
            send_telegram("".join(chunk))
            chunk = []
            total = 0
        chunk.append(add)
        total += len(add)
    if chunk:
        send_telegram("".join(chunk))

    STATE["last_daily_report_date"] = today
    save_state(STATE)

# ====== Kontrola alertů (jen v okně 15:30–21:00) ======
def check_alerts(ts: datetime):
    if not in_alert_window(ts):
        print("Mimo alert okno.")
        return

    today = ts.strftime("%Y-%m-%d")
    sent = STATE.get("alerts_sent", {})  # { "YYYY-MM-DD": { "TICKER:sign": true } }
    sent_today = sent.get(today, {})

    alerts_count = 0

    for ticker in PORTFOLIO:
        open_p, last_p = get_open_and_last(ticker)
        if open_p is None or last_p is None or not open_p:
            continue

        change_pct = ((last_p - open_p) / open_p) * 100
        if abs(change_pct) < ALERT_THRESHOLD:
            continue

        sign = "UP" if change_pct > 0 else "DOWN"
        key = f"{ticker}:{sign}"

        # aby to nechodilo furt dokola: 1× denně pro směr
        if sent_today.get(key):
            continue

        send_alert(ticker, open_p, last_p, change_pct, ts)
        sent_today[key] = True
        alerts_count += 1

    sent[today] = sent_today
    STATE["alerts_sent"] = sent
    save_state(STATE)

    print(f"Hotovo. Odesláno alertů: {alerts_count}")

# ====== MAIN ======
def main():
    ts = now_local()

    # 1) Alerty (pokud jsme v okně)
    check_alerts(ts)

    # 2) Denní report (max 1× denně)
    if is_report_time(ts):
        send_daily_report(ts)

if __name__ == "__main__":
    main()