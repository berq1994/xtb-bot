from pathlib import Path
import json
import datetime as dt

FILE = Path(".state/autonomous_escalation_log.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def log_escalation(level: str, reason: str, payload: dict):
    rows = []
    if FILE.exists():
        try:
            rows = json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    rows.append({
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "level": level,
        "reason": reason,
        "payload": payload,
    })
    FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows

def evaluate_escalation(governance_mode: str, delivery_ok: bool, new_events: int):
    if governance_mode == "SAFE_MODE":
        return {"level": "high", "reason": "SAFE_MODE_ACTIVE"}
    if not delivery_ok:
        return {"level": "medium", "reason": "DELIVERY_FAILED"}
    if int(new_events) >= 3:
        return {"level": "medium", "reason": "HIGH_EVENT_VOLUME"}
    return {"level": "none", "reason": "OK"}
