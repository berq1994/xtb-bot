from pathlib import Path
import json
import datetime as dt

FILE = Path(".state/provider_health.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

DEFAULT = {
    "fmp": {"ok": True, "failures": 0},
    "yahoo": {"ok": True, "failures": 0},
    "rss": {"ok": True, "failures": 0},
    "newsapi": {"ok": True, "failures": 0},
}

def load_health():
    if FILE.exists():
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
            merged = DEFAULT.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    return DEFAULT.copy()

def save_health(data):
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def mark_success(provider: str):
    data = load_health()
    item = data.get(provider, {"ok": True, "failures": 0})
    item["ok"] = True
    item["failures"] = 0
    item["last_success"] = dt.datetime.utcnow().isoformat()
    data[provider] = item
    save_health(data)
    return data

def mark_failure(provider: str):
    data = load_health()
    item = data.get(provider, {"ok": True, "failures": 0})
    item["failures"] = int(item.get("failures", 0)) + 1
    item["ok"] = item["failures"] < 3
    item["last_failure"] = dt.datetime.utcnow().isoformat()
    data[provider] = item
    save_health(data)
    return data
