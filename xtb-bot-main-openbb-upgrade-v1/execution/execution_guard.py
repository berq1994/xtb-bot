def execution_guard(
    governance_mode: str,
    allow_execution: bool,
    paper_mode: bool,
    symbol: str,
):
    if not allow_execution:
        return {"approved": False, "reason": "EXECUTION_BLOCKED_BY_GOVERNANCE"}

    if governance_mode in ["SAFE_MODE", "BLOCKED", "REVIEW_ONLY"]:
        return {"approved": False, "reason": f"GOVERNANCE_MODE_{governance_mode}"}

    if paper_mode:
        return {"approved": True, "reason": "PAPER_MODE_ALLOWED"}

    return {"approved": True, "reason": "LIVE_ALLOWED"}
