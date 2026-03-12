from pathlib import Path
import json
from orchestration.pm_agent import create_plan

STATE = Path(".state")
STATE.mkdir(exist_ok=True)
FILE = STATE / "block4_supervisor_state.json"

def load_state():
    if FILE.exists():
        try:
            return json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"safe_mode": False, "last_plan": None, "last_status": "idle"}

def save_state(state: dict):
    FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def run_supervisor(mode="daily"):
    state = load_state()
    plan = create_plan(mode)
    state["last_plan"] = plan
    state["last_status"] = "planned"
    save_state(state)
    return state
