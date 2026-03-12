def policy_matrix(regime: str, critic_approved: bool, kill_switch: bool):
    if kill_switch:
        return {
            "mode": "SAFE_MODE",
            "allow_new_positions": False,
            "allow_recalibration": False,
            "allow_execution": False,
        }

    if not critic_approved:
        return {
            "mode": "REVIEW_ONLY",
            "allow_new_positions": False,
            "allow_recalibration": True,
            "allow_execution": False,
        }

    if regime == "RISK_OFF":
        return {
            "mode": "DEFENSIVE",
            "allow_new_positions": True,
            "allow_recalibration": True,
            "allow_execution": True,
        }

    return {
        "mode": "NORMAL",
        "allow_new_positions": True,
        "allow_recalibration": True,
        "allow_execution": True,
    }
