# reporting/emailer.py
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from radar.config import RadarConfig


def _send_gmail(cfg: RadarConfig, subject: str, body: str) -> None:
    if not (cfg.email_sender and cfg.email_receiver and cfg.gmail_password):
        print("⚠️ Email zapnutý, ale chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")
        return

    msg = MIMEMultipart()
    msg["From"] = cfg.email_sender
    msg["To"] = cfg.email_receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=40)
    server.ehlo()
    server.starttls()
    server.login(cfg.email_sender, cfg.gmail_password)
    server.sendmail(cfg.email_sender, cfg.email_receiver, msg.as_string())
    server.quit()


def maybe_send_email_report(cfg: RadarConfig, snapshot: dict, now: datetime, tag: str) -> None:
    if not cfg.email_enabled:
        return
    subject = f"MEGA INVESTIČNÍ RADAR – {tag.upper()} ({now.strftime('%Y-%m-%d')})"
    body = "Report byl odeslán do Telegramu.\n\n" + f"Timestamp: {snapshot['meta']['timestamp']}\n"
    try:
        _send_gmail(cfg, subject, body)
        print("✅ Email OK")
    except Exception as e:
        print("❌ Email ERROR:", repr(e))