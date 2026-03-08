def build_production_report(steps: list, briefing_text: str, alert_lines: list, ticket_text: str, journal_text: str, governance_mode: str):
    return {
        "steps": steps,
        "governance_mode": governance_mode,
        "briefing_text": briefing_text,
        "alert_count": len(alert_lines),
        "ticket_text": ticket_text,
        "journal_text": journal_text,
    }

def render_production_report(payload: dict):
    lines = [
        "PRODUCTION RUN REPORT",
        f"Governance mode: {payload.get('governance_mode')}",
        "",
        "Steps:",
    ]
    for step in payload.get("steps", []):
        lines.append(f"- {step}")
    lines.extend([
        "",
        "Briefing:",
        payload.get("briefing_text", ""),
        "",
        f"Alert count: {payload.get('alert_count', 0)}",
        "",
        "Ticket:",
        payload.get("ticket_text", ""),
        "",
        "Journal:",
        payload.get("journal_text", ""),
    ])
    return "\n".join(lines)
