from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import yaml
import yfinance as yf

from radar.config import RadarConfig


def _read_yaml(path: str) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_portfolio(cfg: RadarConfig) -> List[Dict[str, Any]]:
    path = (cfg.portfolio_snapshot_path or "").strip()
    if not path:
        return []
    data = _read_yaml(path)
    arr = data.get("portfolio") or data.get("positions") or []
    if not isinstance(arr, list):
        return []
    out = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        t = str(x.get("ticker") or "").strip().upper()
        if not t:
            continue
        out.append(
            {
                "ticker": t,
                "name": x.get("name"),
                "qty": x.get("qty"),
                "entry": x.get("entry"),
                "currency": x.get("currency"),
                "broker": x.get("broker"),
                "note": x.get("note"),
            }
        )
    return out


def _last_and_prev(ticker: str) -> Optional[tuple[float, float]]:
    try:
        h = yf.Ticker(ticker).history(period="5d", interval="1d")
        if h is None or len(h) < 2:
            return None
        last = float(h["Close"].iloc[-1])
        prev = float(h["Close"].iloc[-2])
        return last, prev
    except Exception:
        return None


def portfolio_snapshot(cfg: RadarConfig, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for p in positions:
        t = str(p.get("ticker") or "").strip().upper()
        if not t:
            continue
        lp = _last_and_prev(t)
        if lp:
            last, prev = lp
            day_pct = ((last - prev) / prev) * 100.0 if prev else None
        else:
            last = None
            day_pct = None

        entry = p.get("entry")
        qty = p.get("qty")
        pnl = None
        pnl_pct = None
        try:
            if entry not in (None, 0, 0.0) and qty not in (None, 0, 0.0) and last is not None:
                entry_f = float(entry)
                qty_f = float(qty)
                pnl = (last - entry_f) * qty_f
                pnl_pct = ((last - entry_f) / entry_f) * 100.0 if entry_f else None
        except Exception:
            pnl = None
            pnl_pct = None

        rows.append(
            {
                "ticker": t,
                "qty": qty,
                "entry": entry,
                "last": last,
                "day_pct": day_pct,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "currency": p.get("currency"),
                "broker": p.get("broker"),
                "name": p.get("name"),
                "note": p.get("note"),
            }
        )

    rows.sort(key=lambda r: (abs(float(r.get("day_pct") or 0.0))), reverse=True)
    return {"count": len(rows), "rows": rows}