def render_activation_report(payload: dict):
    return "\n".join([
        "BLOCK16 ACTIVATION SUITE REPORT",
        f"Telegram ok: {payload.get('telegram_ok')}",
        f"Email ok: {payload.get('email_ok')}",
        f"Sources ok count: {payload.get('sources_ok_count')}",
    ])
