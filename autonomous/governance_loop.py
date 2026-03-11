def autonomous_governance(impact_view: dict):
    hp = impact_view.get("high_priority_count", 0)
    if hp >= 3:
        return {"mode": "REVIEW_ONLY", "manual_xtb_allowed": True, "reason": "HIGH_EVENT_DENSITY"}
    if hp >= 1:
        return {"mode": "REVIEW_ONLY", "manual_xtb_allowed": True, "reason": "RELEVANT_EVENTS_FOUND"}
    return {"mode": "NORMAL", "manual_xtb_allowed": True, "reason": "NO_CRITICAL_EVENT"}
