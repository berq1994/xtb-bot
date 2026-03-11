def build_email_payload(subject_prefix: str, briefing: str, alerts: str, handoff: str):
    subject = f"{subject_prefix} Autonomous Research Delivery"
    body = "\n\n".join([
        "AUTONOMOUS RESEARCH DELIVERY",
        "BRIEFING\n" + briefing,
        "ALERTS\n" + alerts,
        "XTB HANDOFF\n" + handoff,
    ])
    return {
        "subject": subject,
        "body": body,
    }
