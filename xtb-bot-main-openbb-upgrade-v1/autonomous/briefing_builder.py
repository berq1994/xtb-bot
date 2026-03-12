def build_autonomous_briefing(impact_view: dict, governance: dict):
    lines = [
        "AUTONOMOUS RESEARCH BRIEFING",
        f"Governance mode: {governance.get('mode')}",
        f"Důvod: {governance.get('reason')}",
        f"Portfolio relevant events: {impact_view.get('portfolio_relevant_count', 0)}",
        f"High priority events: {impact_view.get('high_priority_count', 0)}",
        "",
        "Top události:",
    ]
    for item in impact_view.get("high_priority", [])[:5]:
        hits = ", ".join(item.get("portfolio_hits", [])) or "-"
        lines.append(f"- [{item.get('kind')}] {item.get('headline')} | hits: {hits} | impact {item.get('impact')} | relevance {item.get('relevance')}")
    return "\n".join(lines)
