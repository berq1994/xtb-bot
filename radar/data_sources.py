# ============================================================
# DATA SOURCES – MEGA INVESTIČNÍ RADAR
# ============================================================

import yfinance as yf


def get_price_data(ticker: str, cfg: dict) -> dict:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d")

        if hist is None or hist.empty:
            return {}

        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_close

        move_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close else 0.0

        return {
            "last": last_close,
            "prev": prev_close,
            "move_pct": move_pct
        }

    except Exception as e:
        print(f"DATA ERROR {ticker}:", e)
        return {}