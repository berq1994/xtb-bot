def render_prod_report(payload: dict):
    lines = [
        "AUTONOMOUS PRODUCTION FLOW REPORT",
        f"Status: {payload.get('state', {}).get('status')}",
        f"Governance mode: {payload.get('governance_mode')}",
        f"Delivery ok: {payload.get('delivery_ok')}",
        f"New events: {payload.get('new_events')}",
        f"Escalation: {payload.get('escalation', {}).get('level')} | {payload.get('escalation', {}).get('reason')}",
        "",
        "Schedule:",
        f"- Poll interval: {payload.get('schedule', {}).get('poll_interval_sec')}",
        f"- Cycle count: {payload.get('schedule', {}).get('cycle_count')}",
        "",
        "Summary:",
        payload.get("summary", ""),
    ]
    return "\n".join(lines)
