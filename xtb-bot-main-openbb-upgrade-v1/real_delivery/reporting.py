def render_delivery_report(payload: dict):
    lines = [
        "REAL DELIVERY REPORT",
        f"Telegram delivered: {payload.get('telegram', {}).get('delivered')}",
        f"Telegram reason: {payload.get('telegram', {}).get('reason')}",
        "",
        f"Email delivered: {payload.get('email', {}).get('delivered')}",
        f"Email reason: {payload.get('email', {}).get('reason')}",
        "",
        f"Briefing length: {payload.get('briefing_length')}",
        f"Alerts length: {payload.get('alerts_length')}",
        f"Handoff length: {payload.get('handoff_length')}",
    ]
    return "\n".join(lines)
