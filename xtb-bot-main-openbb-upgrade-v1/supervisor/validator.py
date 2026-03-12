from pathlib import Path
import json

def validate_backtest_outputs() -> dict:
    eq = Path(".state/equity_curve.json")
    perf = Path(".state/performance_summary.json")

    result = {
        "ok": True,
        "missing_files": [],
        "missing_data_ratio_pct": 0.0,
        "summary": {},
    }

    if not eq.exists():
        result["ok"] = False
        result["missing_files"].append(str(eq))
    if not perf.exists():
        result["ok"] = False
        result["missing_files"].append(str(perf))

    if perf.exists():
        try:
            result["summary"] = json.loads(perf.read_text(encoding="utf-8"))
        except Exception:
            result["ok"] = False

    if result["missing_files"]:
        result["missing_data_ratio_pct"] = 100.0

    return result
