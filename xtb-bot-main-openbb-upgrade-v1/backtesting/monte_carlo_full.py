from __future__ import annotations
from pathlib import Path
import csv
import json
import random
import statistics

STATE = Path(".state")
STATE.mkdir(exist_ok=True)

def _load_trade_pnls(path=".state/trade_log.csv"):
    p = Path(path)
    if not p.exists():
        return []
    pnls = []
    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                pnls.append(float(row.get("pnl", 0.0)))
            except Exception:
                pass
    return pnls

def _percentile(values, p):
    if not values:
        return 0.0
    k = max(0, min(len(values) - 1, int(round((len(values) - 1) * p))))
    return values[k]

def run_monte_carlo_full(simulations=500, trade_log_path=".state/trade_log.csv"):
    pnls = _load_trade_pnls(trade_log_path)
    if not pnls:
        payload = {"ok": False, "message": "trade log empty", "simulations": simulations}
        (STATE / "monte_carlo_full.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    finals = []
    max_dds = []

    for _ in range(simulations):
        seq = random.choices(pnls, k=len(pnls))
        equity = 0.0
        peak = 0.0
        worst_dd = 0.0
        for pnl in seq:
            equity += pnl
            peak = max(peak, equity)
            dd = equity - peak
            worst_dd = min(worst_dd, dd)
        finals.append(equity)
        max_dds.append(worst_dd)

    finals.sort()
    max_dds.sort()

    payload = {
        "ok": True,
        "simulations": simulations,
        "median_final_pnl": round(_percentile(finals, 0.50), 2),
        "p05_final_pnl": round(_percentile(finals, 0.05), 2),
        "p95_final_pnl": round(_percentile(finals, 0.95), 2),
        "avg_final_pnl": round(statistics.mean(finals), 2),
        "median_max_dd": round(_percentile(max_dds, 0.50), 2),
        "p95_max_dd": round(_percentile(max_dds, 0.95), 2),
        "risk_of_negative_run_pct": round(sum(1 for x in finals if x < 0) / len(finals) * 100, 2),
    }

    (STATE / "monte_carlo_full.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
