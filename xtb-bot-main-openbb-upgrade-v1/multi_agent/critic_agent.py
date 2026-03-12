def run_critic(research_payload: dict, signal_payload: dict, risk_payload: dict):
    score = 1.0
    reasons = []

    if not research_payload.get("tickers"):
        score -= 0.4
        reasons.append("Chybí tickery")

    if len(signal_payload.get("top", [])) < 3:
        score -= 0.2
        reasons.append("Málo top signálů")

    if risk_payload.get("drawdown_status") == "HARD_STOP":
        score -= 0.4
        reasons.append("Hard stop drawdown")

    score = max(0.0, round(score, 2))
    approved = score >= 0.75

    return {
        "ok": approved,
        "critic_score": score,
        "reasons": reasons or ["Schváleno"],
        "approved": approved,
    }
