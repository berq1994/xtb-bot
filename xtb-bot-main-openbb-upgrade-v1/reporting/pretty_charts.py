"""Pretty chart rendering for Telegram.

Goal: send **readable, visual** summaries instead of long Markdown tables.

We intentionally keep dependencies minimal (matplotlib + pandas).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import matplotlib

# Headless backend for GitHub Actions
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


@dataclass
class PortfolioRow:
    ticker: str
    last: Optional[float]
    chg_1d_pct: Optional[float]
    pl: Optional[float] = None


def _fmt_price(x: Optional[float]) -> str:
    if x is None:
        return "—"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 100:
        return f"{x:,.2f}"
    return f"{x:,.3f}"


def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "—"
    return f"{x:+.2f}%"


def render_portfolio_table(rows: Iterable[PortfolioRow], out_path: str | Path, title: str = "Portfolio") -> str:
    rows = list(rows)
    df = pd.DataFrame(
        {
            "Ticker": [r.ticker for r in rows],
            "Last": [_fmt_price(r.last) for r in rows],
            "1D": [_fmt_pct(r.chg_1d_pct) for r in rows],
        }
    )

    fig = plt.figure(figsize=(8, max(3, 0.35 * (len(df) + 3))))
    ax = fig.add_subplot(111)
    ax.axis("off")

    ax.set_title(title, fontsize=14, pad=12)

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="center",
        colLoc="center",
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.3)

    # Colorize 1D column
    col_1d = list(df.columns).index("1D")
    for i, r in enumerate(rows, start=1):
        cell = table[i, col_1d]
        if r.chg_1d_pct is None:
            continue
        if r.chg_1d_pct > 0:
            cell.set_facecolor("#e8f5e9")  # light green
        elif r.chg_1d_pct < 0:
            cell.set_facecolor("#ffebee")  # light red

    # Header styling
    for j in range(len(df.columns)):
        h = table[0, j]
        h.set_facecolor("#eeeeee")
        h.set_text_props(weight="bold")

    out_path = str(out_path)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def render_radar_bars(scores: dict[str, float], out_path: str | Path, title: str = "Radar score") -> str:
    if not scores:
        scores = {"—": 0.0}

    items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    labels = [k for k, _ in items]
    vals = [float(v) for _, v in items]

    fig = plt.figure(figsize=(8, max(3, 0.35 * (len(labels) + 3))))
    ax = fig.add_subplot(111)
    ax.barh(labels[::-1], vals[::-1])
    ax.set_title(title, fontsize=14, pad=10)
    ax.set_xlabel("score")

    fig.tight_layout()
    out_path = str(out_path)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def render_portfolio_change_chart(changes: list[tuple[str, float]], title: str = "Portfolio: 1D změna (%)") -> bytes:
    """Create a simple bar chart image (PNG) for 1D % changes."""
    if not changes:
        return b""
    import matplotlib.pyplot as plt

    # sort for nicer view
    changes = sorted(changes, key=lambda x: x[1])
    tickers = [t for t, _ in changes]
    vals = [v for _, v in changes]

    fig, ax = plt.subplots(figsize=(8, max(3, 0.4 * len(tickers))))
    ax.barh(tickers, vals)
    ax.axvline(0.0, linewidth=1)
    ax.set_title(title)
    ax.set_xlabel("%")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()

