from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from typing import Optional

import pandas as pd
import yfinance as yf

_YF_RATE_LIMITED = False


def _mark_rate_limited(msg: str) -> None:
    global _YF_RATE_LIMITED
    if "Too Many Requests" in (msg or ""):
        _YF_RATE_LIMITED = True


def yf_history(ticker: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    global _YF_RATE_LIMITED
    if _YF_RATE_LIMITED:
        return None

    out = io.StringIO()
    err = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            df = yf.Ticker(ticker).history(period=period, interval=interval)
    except Exception as e:
        _mark_rate_limited(str(e))
        _mark_rate_limited(err.getvalue())
        return None

    captured = f"{out.getvalue()}\n{err.getvalue()}"
    _mark_rate_limited(captured)

    if df is None or len(df) == 0:
        return None
    return df
