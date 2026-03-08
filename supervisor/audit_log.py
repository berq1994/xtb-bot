from pathlib import Path
import json
import datetime as dt

STATE = Path(".state")
STATE.mkdir(parents=True, exist_ok=True)
AUDIT = STATE / "supervisor_audit.json"

def read_audit():
    if not AUDIT.exists():
        return []
    try:
        return json.loads(AUDIT.read_text(encoding="utf-8"))
    except Exception:
        return []

def log_event(kind: str, payload: dict):
    rows = read_audit()
    rows.append({
        "timestamp": dt.datetime.utcnow().isoformat(),
        "kind": kind,
        "payload": payload,
    })
    AUDIT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows[-1]
