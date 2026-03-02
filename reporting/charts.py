from __future__ import annotations

from io import BytesIO
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from radar.yf_utils import yf_history


def intraday_chart_png(ticker: str, interval: str = "5m", orb_minutes: int = 15) -> Optional[bytes]:
    df = yf_history(ticker, period="1d", interval=interval)
    if df is None or len(df) < 10:
        return None

    # VWAP
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    v = df["Volume"].clip(lower=0)
    vwap = (tp * v).cumsum() / v.cumsum().replace(0, 1)

    # OR
    step = int(interval.replace("m", ""))
    bars = max(1, orb_minutes // step)
    sub = df.iloc[:bars]
    orh = float(sub["High"].max())
    orl = float(sub["Low"].min())

    fig = plt.figure(figsize=(9, 4))
    ax = fig.add_subplot(111)
    ax.plot(df.index, df["Close"], label="Close")
    ax.plot(df.index, vwap, label="VWAP")
    ax.axhline(orh, linestyle="--", linewidth=1, label=f"ORH {orb_minutes}m")
    ax.axhline(orl, linestyle="--", linewidth=1, label=f"ORL {orb_minutes}m")
    ax.set_title(f"{ticker} intraday ({interval})")
    ax.legend()
    ax.grid(True, alpha=0.25)

    buf = BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def safe_intraday_chart_png(ticker: str, interval: str = "5m", orb_minutes: int = 15) -> Optional[bytes]:
    try:
        return intraday_chart_png(ticker, interval=interval, orb_minutes=orb_minutes)
    except Exception:
        return None
