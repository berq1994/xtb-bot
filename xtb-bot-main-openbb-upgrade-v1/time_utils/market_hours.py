from datetime import datetime
import pytz

TZ = pytz.timezone("Europe/Prague")

EU_SYMBOLS = {"CEZ.PR", "EON.DE", "CSG"}
US_SYMBOLS = {"SPY", "QQQ", "SMH", "NVDA", "AMD", "TSLA", "AAPL", "MSFT", "META", "GOOGL", "AMZN", "IBIT"}
CRYPTO_SYMBOLS = {"BTC-USD"}

def _to_local(now=None):
    now = now or datetime.utcnow().replace(tzinfo=pytz.utc)
    return now.astimezone(TZ)

def is_us_market_open(now=None):
    now = _to_local(now)
    if now.weekday() >= 5:
        return False
    mins = now.hour * 60 + now.minute
    return 15 * 60 + 30 <= mins < 22 * 60

def is_eu_market_open(now=None):
    now = _to_local(now)
    if now.weekday() >= 5:
        return False
    mins = now.hour * 60 + now.minute
    return 9 * 60 <= mins < 17 * 60 + 30

def is_symbol_tradeable(symbol: str, now=None, btc_mode="market_hours_only"):
    s = (symbol or "").upper()
    if s in EU_SYMBOLS:
        return is_eu_market_open(now)
    if s in US_SYMBOLS:
        return is_us_market_open(now)
    if s in CRYPTO_SYMBOLS:
        return True if btc_mode == "24/7" else is_us_market_open(now)
    return False
