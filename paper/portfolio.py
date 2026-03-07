import json
from pathlib import Path

STATE = Path(".state")
STATE.mkdir(exist_ok=True)
TRADE_LOG = STATE / "trade_log.json"
EQUITY_LOG = STATE / "equity_curve.json"

def _load(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

def _save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_trade_log():
    return _load(TRADE_LOG, {"open": [], "closed": []})

def save_trade_log(data):
    _save(TRADE_LOG, data)

def load_equity():
    return _load(EQUITY_LOG, {"equity": 100000.0, "curve": []})

def save_equity(data):
    _save(EQUITY_LOG, data)
