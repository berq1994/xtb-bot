def choose_fallback(governance_payload: dict, health_payload: dict):
    if not health_payload.get("healthy", False):
        return {"fallback_mode": "MINIMAL_REPORTING_ONLY"}
    if governance_payload.get("kill_switch", {}).get("kill_switch", False):
        return {"fallback_mode": "SAFE_MODE_NO_EXECUTION"}
    if governance_payload.get("policy", {}).get("mode") == "REVIEW_ONLY":
        return {"fallback_mode": "REVIEW_QUEUE"}
    return {"fallback_mode": "NONE"}
