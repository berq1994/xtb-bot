def run_governance_agent_v2(critic_payload: dict, risk_payload: dict):
    if not risk_payload.get("risk_ok", False):
        return {"mode": "SAFE_MODE", "allow_trade": False}
    if critic_payload.get("approved", False):
        return {"mode": "REVIEW_ONLY", "allow_trade": True}
    return {"mode": "SAFE_MODE", "allow_trade": False}
