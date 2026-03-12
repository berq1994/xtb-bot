def run_kill_switch_agent(hard_risk_event: bool = False):
    return {
        "kill_switch": bool(hard_risk_event),
        "reason": "HARD_EVENT" if hard_risk_event else "OK",
    }


