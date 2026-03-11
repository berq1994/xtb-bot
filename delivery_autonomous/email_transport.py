import os

def send_email_payload(payload: dict):
    smtp_host = os.getenv("EMAIL_SMTP_HOST")
    smtp_user = os.getenv("EMAIL_SMTP_USER")
    smtp_pass = os.getenv("EMAIL_SMTP_PASS")
    smtp_to = os.getenv("EMAIL_TO")
    enabled = str(os.getenv("EMAIL_SEND_ENABLED", "false")).lower() in ["1", "true", "yes", "on"]

    ready = bool(smtp_host) and bool(smtp_user) and bool(smtp_pass) and bool(smtp_to) and enabled
    # transport scaffold only; no live SMTP send here
    return {
        "delivered": False,
        "transport": "smtp_stub",
        "ready": ready,
        "reason": "SMTP_READY_BUT_NOT_IMPLEMENTED" if ready else "MISSING_OR_DISABLED_EMAIL_CONFIG",
        "subject_preview": payload.get("subject"),
    }
