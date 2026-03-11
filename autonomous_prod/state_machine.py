from pathlib import Path
import json
import datetime as dt

FILE = Path(".state/autonomous_prod_state.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

DEFAULT = {
    "last_run_utc": None,
    "status": "IDLE",
    "last_governance_mode": "UNKNOWN",
    "last_delivery_ok": False,
    "cycle_count": 0,
}

def load_state():
    if FILE.exists():
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
            merged = DEFAULT.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    return DEFAULT.copy()

def update_state(status: str, governance_mode: str, delivery_ok: bool):
    state = load_state()
    state["last_run_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    state["status"] = status
    state["last_governance_mode"] = governance_mode
    state["last_delivery_ok"] = bool(delivery_ok)
    state["cycle_count"] = int(state.get("cycle_count", 0)) + 1
    FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state
