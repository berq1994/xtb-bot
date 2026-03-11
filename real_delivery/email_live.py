import os
import smtplib
from email.message import EmailMessage

def send_email_live(subject: str, body: str):
    host = os.getenv("EMAIL_SMTP_HOST")
    port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    user = os.getenv("EMAIL_SMTP_USER")
    pwd = os.getenv("EMAIL_SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM")
    email_to = os.getenv("EMAIL_TO")
    enabled = str(os.getenv("EMAIL_SEND_ENABLED", "false")).lower() in ["1","true","yes","on"]

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
