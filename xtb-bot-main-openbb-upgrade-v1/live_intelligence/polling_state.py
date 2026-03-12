from pathlib import Path
import json
import datetime as dt

FILE = Path(".state/live_intelligence_polling.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def save_polling_snapshot(rows: list):
    payload = {
        "last_poll_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "count": len(rows),
        "rows": rows,
    }
    FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
