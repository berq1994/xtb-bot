import json
from pathlib import Path
import pandas as pd

STATE = Path(".state")
STATE.mkdir(exist_ok=True)

def save_equity_curve(df: pd.DataFrame):
    path = STATE / "equity_curve.json"
    data = [{"date": str(idx.date()), "equity": float(val)} for idx, val in df["equity"].items()]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def save_performance_summary(summary: dict):
    path = STATE / "performance_summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

def save_trade_log(trades: list):
    path = STATE / "trade_log.csv"
    if not trades:
        path.write_text("date,symbol,entry,exit,pnl\n", encoding="utf-8")
        return
    lines = ["date,symbol,entry,exit,pnl"]
    for t in trades:
        lines.append(f"{t['date']},{t['symbol']},{t['entry']},{t['exit']},{t['pnl']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
