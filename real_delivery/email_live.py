import os
import smtplib
from email.message import EmailMessage


def _first(*keys: str) -> str:
    for key in keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def send_email_live(subject: str, body: str):
    host = _first("EMAIL_SMTP_HOST") or "smtp.gmail.com"
    port = int(_first("EMAIL_SMTP_PORT") or "587")
    user = _first("EMAIL_SMTP_USER", "EMAIL_SENDER")
    pwd = _first("EMAIL_SMTP_PASS", "GMAILPASSWORD")
    email_from = _first("EMAIL_FROM", "EMAIL_SMTP_USER", "EMAIL_SENDER")
    email_to = _first("EMAIL_TO", "EMAIL_RECEIVER")
    enabled = str(_first("EMAIL_SEND_ENABLED", "EMAIL_ENABLED") or "false").lower() in ["1", "true", "yes", "on"]

    ready = all([host, user, pwd, email_from, email_to]) and enabled
    if not ready:
        return {
            "delivered": False,
            "ready": False,
            "transport": "smtp_live",
            "reason": "MISSING_OR_DISABLED_EMAIL_CONFIG",
        }

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            if user and pwd:
                server.login(user, pwd)
            server.send_message(msg)
        return {
            "delivered": True,
            "ready": True,
            "transport": "smtp_live",
            "reason": "OK",
        }
    except Exception as e:
        return {
            "delivered": False,
            "ready": True,
            "transport": "smtp_live",
            "reason": f"SMTP_ERROR: {e}",
        }
