def build_executive_report(summary: dict, ai_rows: list) -> str:
    lines = [
        "📌 EXECUTIVE REPORT",
        f"Režim trhu: {summary.get('regime','n/a')}",
        f"Confidence: {summary.get('regime_confidence','n/a')}",
        f"Portfolio VaR: {summary.get('portfolio_var','n/a')}",
        f"Max DD limit: {summary.get('max_dd_limit','n/a')}",
        "",
        "Top AI kandidáti:"
    ]
    for row in ai_rows[:5]:
        lines.append(
            f"- {row['symbol']} | score {row['final_score']} | sentiment {row['sentiment']['label']} | vol {row['volatility']['state']}"
        )
    lines.append("")
    lines.append("Nejde o investiční doporučení, ale o systematický AI report.")
    return "\n".join(lines)
