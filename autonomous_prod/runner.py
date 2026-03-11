import json
from pathlib import Path
from autonomous_prod.state_machine import update_state, load_state
from autonomous_prod.escalation import evaluate_escalation, log_escalation
from autonomous_prod.scheduler import build_schedule_view

def _read_json(path_str: str, default):
    path = Path(path_str)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default

def run_autonomous_production_flow():
    a15 = _read_json(".state/block15a_autonomous_run.json", {})
    b15 = _read_json(".state/block15b_delivery.json", {})

    governance_mode = a15.get("governance", {}).get("mode", "UNKNOWN")
    new_events = int(a15.get("new_events", 0) or 0)
    delivery_ok = bool(
        b15.get("telegram_result", {}).get("delivered", False)
        or b15.get("email_result", {}).get("delivered", False)
    )

    status = "RUNNING"
    if governance_mode == "SAFE_MODE":
        status = "SAFE_MODE"
    elif governance_mode == "REVIEW_ONLY":
        status = "REVIEW_ONLY"
    elif governance_mode == "NORMAL":
        status = "NORMAL"

    state = update_state(status, governance_mode, delivery_ok)
    escalation = evaluate_escalation(governance_mode, delivery_ok, new_events)
    if escalation["level"] != "none":
        log_escalation(escalation["level"], escalation["reason"], {
            "governance_mode": governance_mode,
            "delivery_ok": delivery_ok,
            "new_events": new_events,
        })

    schedule = build_schedule_view(300, state["cycle_count"])
    summary = "Autonomous production flow sjednotil research, delivery a governance do jednoho běhu."

    return {
        "governance_mode": governance_mode,
        "new_events": new_events,
        "delivery_ok": delivery_ok,
        "state": state,
        "escalation": escalation,
        "schedule": schedule,
        "summary": summary,
    }
