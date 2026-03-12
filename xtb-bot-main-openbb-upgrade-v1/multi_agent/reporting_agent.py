def build_report(plan, research_payload, signal_payload, risk_payload, critic_payload):
    lines = [
        "🤖 MULTI-AGENT REPORT",
        f"Plán kroků: {len(plan)}",
        f"Makro režim: {research_payload.get('macro_regime', 'n/a')}",
        f"Portfolio VaR: {risk_payload.get('portfolio_var_pct', 'n/a')}%",
        f"Drawdown status: {risk_payload.get('drawdown_status', 'n/a')}",
        f"Critic score: {critic_payload.get('critic_score', 'n/a')}",
        "",
        "Top signály:"
    ]
    for row in signal_payload.get("top", [])[:5]:
        lines.append(
            f"- {row['symbol']} | score {row['final_score']} | sentiment {row['sentiment']['label']} | režim {row['regime']['regime']}"
        )
    lines.append("")
    lines.append("Nejde o investiční doporučení.")
    return "\n".join(lines)
