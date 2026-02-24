# ============================================================
# DATA SOURCES – MEGA INVESTIČNÍ RADAR
# ============================================================

import yfinance as yf


def get_price_data(ticker: str, cfg: dict) -> dict:
    try:
        t = yf.Ticker(ticker)

        hist = t.history(period="5d", interval="1d")

        if hist is None or hist.empty: