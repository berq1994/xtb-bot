def evaluate_kill_switch(
    current_drawdown_pct: float,
    max_drawdown_hard_pct: float,
    risk_of_negative_run_pct: float,
    critic_approved: bool,
    missing_ratio_pct: float,
):
    active = False
    reasons = []

    if current_drawdown_pct <= -abs(max_drawdown_hard_pct):
        active = True
        reasons.append("HARD_DRAWDOWN_LIMIT")

    if risk_of_negative_run_pct >= 70:
        active = True
        reasons.append("MC_RISK_TOO_HIGH")

    if not critic_approved:
        reasons.append("CRITIC_NOT_APPROVED")

    if missing_ratio_pct >= 25:
        active = True
        reasons.append("DATA_QUALITY_TOO_LOW")

    return {
        "kill_switch": active,
        "reasons": reasons or ["OK"],
    }
