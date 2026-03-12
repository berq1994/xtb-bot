def build_report(plan, research_payload, signal_payload, risk_payload, critic_payload):
    lines = [
        "🏦 BLOCK 4 ENTERPRISE REPORT",
        f"Critic approved: {critic_payload.get('approved')}",
        f"Critic score: {critic_payload.get('score')}",
        f"Portfolio VaR: {risk_payload.get('var', {}).get('var_pct')}",
        f"Drawdown status: {risk_payload.get('drawdown', {}).get('status')}",
        "",
        "Top signály:"
    ]
    for row in signal_payload.get("top", [])[:5]:
        lines.append(f"- {row['symbol']} | score {row['score']} | model {row['model']}")
    return "\n".join(lines)
