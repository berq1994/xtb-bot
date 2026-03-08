def transition_policy(critic_band: str, performance_band: str):
    if critic_band == "NORMAL_READY" and performance_band == "NORMAL_READY":
        return {
            "final_mode": "NORMAL",
            "allow_execution": True,
            "allow_new_positions": True,
            "allow_recalibration": True,
            "reason": "ALL_GREEN",
        }

    if critic_band in ["NORMAL_READY", "REVIEW_READY"] and performance_band in ["NORMAL_READY", "REVIEW_READY"]:
        return {
            "final_mode": "REVIEW_ONLY",
            "allow_execution": False,
            "allow_new_positions": False,
            "allow_recalibration": True,
            "reason": "SOFT_GREEN",
        }

    return {
        "final_mode": "SAFE_MODE",
        "allow_execution": False,
        "allow_new_positions": False,
        "allow_recalibration": False,
        "reason": "THRESHOLDS_NOT_MET",
    }
