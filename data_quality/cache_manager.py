from pathlib import Path
import json
import datetime as dt

CACHE = Path(".state/data_cache")
CACHE.mkdir(parents=True, exist_ok=True)

def cache_put(key: str, payload: dict):
    obj = {
        "saved_at": dt.datetime.utcnow().isoformat(),
        "payload": payload,
    }
    (CACHE / f"{key}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def cache_get(key: str):
    path = CACHE / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
