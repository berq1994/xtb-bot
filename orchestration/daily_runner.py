def build_daily_orchestration(briefing_text: str, alert_lines: list, ticket_text: str, journal_note: str):
    return {
        "steps": [
            "live intelligence loaded",
            "briefing prepared",
            "alerts prepared",
            "manual ticket prepared",
            "journal note prepared",
        ],
        "briefing_text": briefing_text,
        "alert_count": len(alert_lines),
        "ticket_text": ticket_text,
        "journal_note": journal_note,
    }
