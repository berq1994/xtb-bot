from pathlib import Path
import json

STATE = Path(".state")
STATE.mkdir(parents=True, exist_ok=True)
FILE = STATE / "supervisor_state.json"

DEFAULT = {
    "safe_mode": False,
    "consecutive_failures": 0,
    "last_tasks": [],
    "last_status": "idle",
}

def load_state():
    if not FILE.exists():
        return DEFAULT.copy()
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        merged = DEFAULT.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULT.copy()

def save_state(state: dict):
    FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
