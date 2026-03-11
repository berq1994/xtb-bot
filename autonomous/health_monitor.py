from pathlib import Path
import json
import datetime as dt

FILE = Path(".state/autonomous_health.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def write_health(ok: bool, cycle: int, details: dict):
    payload = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "ok": bool(ok),
        "cycle": int(cycle),
        "details": details,
    }
    FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
