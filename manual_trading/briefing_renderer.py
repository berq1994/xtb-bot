def render_briefing_text(briefing: dict):
    lines = [
        "XTB DAILY BRIEFING",
        f"Final mode: {briefing['final_mode']}",
        f"Governance mode: {briefing['governance_mode']}",
        f"Poznámka k trhu: {briefing['market_note']}",
        "",
        "Top watchlist:",
    ]
    for row in briefing["top_watchlist"]:
        lines.append(f"- #{row['rank']} {row['symbol']} | score {row['score']}")
    lines.append("")
    lines.append("Dnešní akce:")
    for item in briefing["actions"]:
        lines.append(f"- {item}")
    return "\n".join(lines)
