from pathlib import Path
import json
import datetime as dt

FILE = Path(".state/block10d_trade_journal.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def load_journal():
    if FILE.exists():
        try:
            return json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def append_trade(entry: dict):
    rows = load_journal()
    rows.append({
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        **entry
    })
    FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows
