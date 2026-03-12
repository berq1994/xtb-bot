from __future__ import annotations
from pathlib import Path
import json
import math
import pandas as pd

STATE = Path(".state")
STATE.mkdir(exist_ok=True)

def _build_windows(index, train_months=24, test_months=6):
    if len(index) < 120:
        return []
    step = max(20, test_months * 21)
    train_len = max(60, train_months * 21)
    test_len = max(20, test_months * 21)

    windows = []
    start = 0
    while start + train_len + test_len <= len(index):
        train_slice = (start, start + train_len)
        test_slice = (start + train_len, start + train_len + test_len)
        windows.append({"train": train_slice, "test": test_slice})
        start += step
    return windows

def _compute_metrics(equity: pd.Series):
    if equity.empty or len(equity) < 2:
        return {"return_pct": 0.0, "max_dd_pct": 0.0, "vol_pct": 0.0}

    returns = equity.pct_change().dropna()
    total_return = (equity.iloc[-1] / equity.iloc[0] - 1.0) * 100 if equity.iloc[0] else 0.0
    running_max = equity.cummax()
    dd = (equity / running_max - 1.0).min() * 100
    vol = returns.std() * (252 ** 0.5) * 100 if not returns.empty else 0.0
    return {
        "return_pct": round(float(total_return), 2),
        "max_dd_pct": round(float(dd), 2),
        "vol_pct": round(float(vol), 2),
    }

def run_walk_forward_full(equity_curve_path=".state/equity_curve.json", train_months=24, test_months=6):
    path = Path(equity_curve_path)
    if not path.exists():
        return {"ok": False, "message": "equity_curve.json not found", "windows": []}

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not raw:
        return {"ok": False, "message": "equity curve empty", "windows": []}

    df = pd.DataFrame(raw)
    if "date" not in df.columns or "equity" not in df.columns:
        return {"ok": False, "message": "invalid equity curve format", "windows": []}

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    eq = pd.to_numeric(df["equity"], errors="coerce").dropna()

    windows = _build_windows(eq.index, train_months=train_months, test_months=test_months)
    out = []

    for idx, w in enumerate(windows, start=1):
        train_eq = eq.iloc[w["train"][0]:w["train"][1]]
        test_eq = eq.iloc[w["test"][0]:w["test"][1]]

        train_metrics = _compute_metrics(train_eq)
        test_metrics = _compute_metrics(test_eq)

        out.append({
            "window": idx,
            "train_start": str(train_eq.index[0].date()) if not train_eq.empty else None,
            "train_end": str(train_eq.index[-1].date()) if not train_eq.empty else None,
            "test_start": str(test_eq.index[0].date()) if not test_eq.empty else None,
            "test_end": str(test_eq.index[-1].date()) if not test_eq.empty else None,
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
        })

    summary = {
        "ok": True,
        "windows_count": len(out),
        "avg_test_return_pct": round(sum(w["test_metrics"]["return_pct"] for w in out) / len(out), 2) if out else 0.0,
        "avg_test_max_dd_pct": round(sum(w["test_metrics"]["max_dd_pct"] for w in out) / len(out), 2) if out else 0.0,
        "avg_test_vol_pct": round(sum(w["test_metrics"]["vol_pct"] for w in out) / len(out), 2) if out else 0.0,
    }

    payload = {"summary": summary, "windows": out}
    (STATE / "walk_forward_full.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
