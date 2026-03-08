from pathlib import Path
import json
import datetime as dt

TRACKER = Path(".state/experiment_log.json")
TRACKER.parent.mkdir(parents=True, exist_ok=True)

def log_experiment(kind: str, payload: dict):
    data = []
    if TRACKER.exists():
        try:
            data = json.loads(TRACKER.read_text(encoding="utf-8"))
        except Exception:
            data = []
    data.append({
        "kind": kind,
        "payload": payload,
        "timestamp": dt.datetime.utcnow().isoformat()
    })
    TRACKER.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
