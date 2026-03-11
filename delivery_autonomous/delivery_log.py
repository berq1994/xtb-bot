from pathlib import Path
import json
import datetime as dt

FILE = Path(".state/autonomous_delivery_log.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def log_delivery(payload: dict):
    rows = []
    if FILE.exists():
        try:
            rows = json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    rows.append({
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        **payload
    })
    FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows
