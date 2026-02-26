# radar/backfill.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Any, List, Optional

import yfinance as yf

from radar.config import RadarConfig
from radar.universe import resolved_universe


def _to_iso_end(end_iso: str, now: datetime) -> str:
    end_iso = (end_iso or "").strip()
    if not end_iso:
        return now.strftime("%Y-%m-%d")
    return end_iso


def backfill_history(cfg: RadarConfig, now: datetime, st=None, start_iso: str = "2025-01-01", end_iso: str = "") -> Dict[str, Any]:
    """
    (2) Backfill:
    - stáhne daily data pro resolved tickery
    - uloží CSV do {state_dir}/history/{ticker}.csv
    """
    end_iso = _to_iso_end(end_iso, now)

    state_dir = getattr(cfg, "state_dir", ".state") or ".state"
    history_dir = os.path.join(state_dir, "history")
    os.makedirs(history_dir, exist_ok=True)

    resolved, _ = resolved_universe(cfg, universe=None)

    ok = 0
    fail = 0
    failed: List[str] = []

    # Limit: max 60 tickerů na jeden backfill run, ať to nevyteče
    for t in resolved[:60]:
        try:
            df = yf.download(
                t,
                start=start_iso,
                end=end_iso,
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if df is None or df.empty:
                fail += 1
                failed.append(t)
                continue

            path = os.path.join(history_dir, f"{t}.csv")
            df.to_csv(path)
            ok += 1
        except Exception:
            fail += 1
            failed.append(t)

    return {
        "start": start_iso,
        "end": end_iso,
        "tickers_total": min(len(resolved), 60),
        "ok": ok,
        "fail": fail,
        "failed": failed,
        "history_dir": history_dir,
    }