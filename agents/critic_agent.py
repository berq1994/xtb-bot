def run_critic(research_payload, signal_payload, risk_payload):
    score = 1.0
    reasons = []
    if not research_payload.get("market"):
        score -= 0.3
        reasons.append("ChybĂ­ market data")
    if len(signal_payload.get("top", [])) < 3:
        score -= 0.2
        reasons.append("MĂˇlo top signĂˇlĹŻ")
    if risk_payload.get("drawdown", {}).get("status") == "HARD_STOP":
        score -= 0.5
        reasons.append("Hard stop")
    return {"approved": score >= 0.7, "score": round(max(0.0, score), 2), "reasons": reasons or ["OK"]}


