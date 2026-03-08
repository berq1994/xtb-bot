def approval_flow(
    runtime_mode: str,
    manual_flag_present: bool,
    governance_mode: str,
    final_decision_mode: str,
):
    if runtime_mode == "paper":
        return {"approved": True, "activation_mode": "PAPER", "reason": "PAPER_MODE"}

    if runtime_mode == "live_locked":
        return {"approved": False, "activation_mode": "LIVE_LOCKED", "reason": "LIVE_LOCKED"}

    if runtime_mode == "semi_live":
        if not manual_flag_present:
            return {"approved": False, "activation_mode": "SEMI_LIVE_BLOCKED", "reason": "MANUAL_FLAG_REQUIRED"}
        if governance_mode not in ["NORMAL", "DEFENSIVE"]:
            return {"approved": False, "activation_mode": "SEMI_LIVE_BLOCKED", "reason": "GOVERNANCE_NOT_READY"}
        if final_decision_mode != "NORMAL":
            return {"approved": False, "activation_mode": "SEMI_LIVE_BLOCKED", "reason": "FINAL_DECISION_NOT_NORMAL"}
        return {"approved": True, "activation_mode": "SEMI_LIVE", "reason": "APPROVED"}

    return {"approved": False, "activation_mode": "UNKNOWN", "reason": "UNKNOWN_MODE"}
