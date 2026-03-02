from __future__ import annotations

import os
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib
from typing import Any, Dict, Optional

from radar.config import RadarConfig


def maybe_send_email_report(cfg: RadarConfig, payload: Dict[str, Any], now: datetime, tag: str = "") -> None:
    if not cfg.email_enabled:
        return

    sender = (os.getenv("EMAIL_SENDER") or cfg.email_sender or "").strip()
    receiver = (os.getenv("EMAIL_RECEIVER") or cfg.email_receiver or "").strip()
    pwd = (os.getenv("GMAILPASSWORD") or cfg.gmail_password or "").strip()
    if not sender or not receiver or not pwd:
        return

    subject = f"Radar report: {tag} ({now.strftime('%Y-%m-%d %H:%M')})"
    body = str(payload.get("rendered_text") or "")

    png_bytes = payload.get("png_bytes")
    filename = str(payload.get("filename") or "chart.png")

    msg = MIMEMultipart()
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if isinstance(png_bytes, (bytes, bytearray)) and len(png_bytes) > 0:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(bytes(png_bytes))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(sender, pwd)
            s.sendmail(sender, [receiver], msg.as_string())
    except Exception:
        return
