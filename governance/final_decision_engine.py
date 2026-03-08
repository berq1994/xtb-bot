def final_decision_engine(
    critic_payload: dict,
    governance_payload: dict,
    performance_integration: dict,
):
    kill_switch = bool(governance_payload.get("kill_switch", {}).get("kill_switch", False))
    critic_ok = bool(critic_payload.get("approved", False))
    integrated_ok = bool(performance_integration.get("approved", False))

    if kill_switch:
        return {
            "final_mode": "BLOCKED",
            "allow_execution": False,
            "allow_new_positions": False,
            "allow_recalibration": False,
            "reason": "KILL_SWITCH_ACTIVE",
        }

    if not critic_ok and not integrated_ok:
        return {
            "final_mode": "SAFE_MODE",
            "allow_execution": False,
            "allow_new_positions": False,
            "allow_recalibration": False,
            "reason": "CRITIC_AND_PERFORMANCE_BLOCK",
        }

    if not critic_ok or not integrated_ok:
        return {
            "final_mode": "REVIEW_ONLY",
            "allow_execution": False,
            "allow_new_positions": False,
            "allow_recalibration": True,
            "reason": "REVIEW_REQUIRED",
        }

    return {
        "final_mode": "NORMAL",
        "allow_execution": True,
        "allow_new_positions": True,
        "allow_recalibration": True,
        "reason": "APPROVED",
    }
