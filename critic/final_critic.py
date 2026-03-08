def run_final_critic(
    performance_integration: dict,
    walk_forward: dict,
    monte_carlo: dict,
    data_gate: dict,
):
    score = 1.0
    reasons = []

    if not performance_integration.get("approved", False):
        score -= 0.35
        reasons.append("PERFORMANCE_NOT_APPROVED")

    avg_test_return = float(walk_forward.get("summary", {}).get("avg_test_return_pct", 0.0) or 0.0)
    if avg_test_return < 0:
        score -= 0.20
        reasons.append("NEGATIVE_WALK_FORWARD")

    risk_negative = float(monte_carlo.get("risk_of_negative_run_pct", 100.0) or 100.0)
    if risk_negative > 25:
        score -= 0.20
        reasons.append("MC_RISK_ELEVATED")

    if not data_gate.get("approved", False):
        score -= 0.25
        reasons.append("DATA_GATE_NOT_APPROVED")

    score = max(0.0, round(score, 2))
    approved = score >= 0.75

    return {
        "approved": approved,
        "score": score,
        "reasons": reasons or ["OK"],
    }
