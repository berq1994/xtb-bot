def build_telegram_payload(briefing: str, alerts: str, handoff: str):
    parts = [
        "AUTONOMOUS DELIVERY",
        "",
        "BRIEFING:",
        briefing[:1500],
        "",
        "ALERTS:",
        alerts[:1200],
        "",
        "XTB HANDOFF:",
        handoff[:1200],
    ]
    return "\n".join(parts)[:4096]
