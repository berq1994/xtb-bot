# reporting/charts.py
from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

import matplotlib.pyplot as plt
import yfinance as yf


def price_chart_png(
    ticker: str,
    days: int = 60,
    title: Optional[str] = None,
    show_volume: bool = True,
) -> bytes:
    """
    Vygeneruje jednoduchý, čistý price chart do PNG (bytes).
    - Bez specifických barev (default matplotlib).
    - Používá yfinance history(period=...).

    days: 30/60/90 (doporučeno)
    """
    t = (ticker or "").strip()
    if not t:
        raise ValueError("ticker empty")

    # yfinance period string
    if days <= 7:
        period = "7d"
    elif days <= 30:
        period = "1mo"
    elif days <= 60:
        period = "3mo"
    elif days <= 90:
        period = "6mo"
    else:
        period = "1y"

    h = yf.Ticker(t).history(period=period, interval="1d")
    if h is None or len(h) < 5:
        raise RuntimeError(f"not enough data for {t}")

    # vezmeme posledních N dní, pokud máme víc
    if len(h) > days:
        h = h.tail(days)

    close = h["Close"]
    vol = h["Volume"] if "Volume" in h.columns else None

    # --- plot ---
    plt.figure(figsize=(10, 4.5))
    plt.plot(close.index, close.values, linewidth=1.5)

    ttl = title or f"{t} — Close ({len(close)}D)"
    plt.title(ttl)
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.grid(True, alpha=0.25)

    # volume overlay (druhý axis) – jednoduché a čitelné
    if show_volume and vol is not None:
        ax1 = plt.gca()
        ax2 = ax1.twinx()
        ax2.fill_between(vol.index, vol.values, step="pre", alpha=0.15)
        ax2.set_ylabel("Volume")
        # ztlumíme tick labely
        for tick in ax2.get_yticklabels():
            tick.set_alpha(0.4)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=140)
    plt.close()
    return buf.getvalue()


def safe_price_chart_png(
    ticker: str,
    days: int = 60,
    title: Optional[str] = None,
    show_volume: bool = True,
) -> Optional[bytes]:
    """Bezpečná varianta: nevyhazuje výjimky, vrací None když se nepovede."""
    try:
        return price_chart_png(ticker=ticker, days=days, title=title, show_volume=show_volume)
    except Exception:
        return None