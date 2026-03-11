def build_delivery_report(telegram_result: dict, email_result: dict, briefing_len: int, alerts_len: int, handoff_len: int):
    lines = [
        "AUTONOMOUS DELIVERY REPORT",
        f"Telegram delivered: {telegram_result.get('delivered')}",
        f"Telegram ready: {telegram_result.get('ready')}",
        f"Telegram reason: {telegram_result.get('reason')}",
        "",
        f"Email delivered: {email_result.get('delivered')}",
        f"Email ready: {email_result.get('ready')}",
        f"Email reason: {email_result.get('reason')}",
        "",
        f"Briefing length: {briefing_len}",
        f"Alerts length: {alerts_len}",
        f"Handoff length: {handoff_len}",
    ]
    return "\n".join(lines)
