def semi_live_decision(tuned: dict):
    approved = all(bool(v) for v in tuned.values())
    return {
        "approved": approved,
        "reason": "APPROVED" if approved else "THRESHOLD_REVIEW_REQUIRED",
        "checks": tuned,
    }
