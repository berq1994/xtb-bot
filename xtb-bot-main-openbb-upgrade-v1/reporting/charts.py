import os
from typing import Optional
import yfinance as yf
import matplotlib.pyplot as plt


def make_price_chart(ticker: str, days: int = 30, out_dir: str = ".state") -> Optional[str]:
    try:
        h = yf.Ticker(ticker).history(period=f"{days}d", interval="1d")
        if h is None or h.empty:
            return None

        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{ticker}_chart.png")

        plt.figure(figsize=(8, 4))
        plt.plot(h.index, h["Close"])
        plt.title(f"{ticker} – cena (posledních {days} dní)")
        plt.xlabel("Datum")
        plt.ylabel("Cena")
        plt.tight_layout()
        plt.savefig(path)
        plt.close()

        return path
    except Exception:
        return None