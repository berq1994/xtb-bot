from pathlib import Path
import json
import datetime as dt

STATE = Path(".state/feature_store")
STATE.mkdir(parents=True, exist_ok=True)

def save_feature_snapshot(name: str, payload: dict):
    path = STATE / f"{name}.json"
    wrapped = {
        "saved_at": dt.datetime.utcnow().isoformat(),
        "payload": payload,
    }
    path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def load_feature_snapshot(name: str):
    path = STATE / f"{name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("payload")
    except Exception:
        return None
