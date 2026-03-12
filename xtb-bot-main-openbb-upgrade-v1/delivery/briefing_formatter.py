def format_briefing(briefing: dict):
    lines = [
        briefing.get("title", "Live Intelligence Briefing"),
        f"GEO: {briefing.get('geo_count', 0)} | EARNINGS: {briefing.get('earnings_count', 0)} | CORPORATE: {briefing.get('corporate_count', 0)} | MACRO: {briefing.get('macro_count', 0)}",
        "",
        "Top položky:",
    ]
    for item in briefing.get("top_items", []):
        lines.append(f"- [{item['kind']}] {item['headline']} | impact {item['impact']} | relevance {item['relevance']}")
    return "\n".join(lines)
