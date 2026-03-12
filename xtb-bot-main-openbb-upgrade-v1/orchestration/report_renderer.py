def render_orchestration_report(payload: dict):
    lines = [
        "DAILY ORCHESTRATION REPORT",
        "",
        "Kroky:",
    ]
    for step in payload.get("steps", []):
        lines.append(f"- {step}")
    lines.append("")
    lines.append("Briefing:")
    lines.append(payload.get("briefing_text", ""))
    lines.append("")
    lines.append(f"Počet alertů: {payload.get('alert_count', 0)}")
    lines.append("")
    lines.append("Ticket:")
    lines.append(payload.get("ticket_text", ""))
    lines.append("")
    lines.append("Journal:")
    lines.append(payload.get("journal_note", ""))
    return "\n".join(lines)
