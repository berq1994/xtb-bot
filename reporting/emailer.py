# reporting/emailer.py
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from radar.config import RadarConfig


def _read_text(path: str, default: str = "") -> str:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return default


def _write_text(path: str, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def maybe_send_email_report(cfg: RadarConfig, snapshot_or_payload, now: datetime, tag: str):
    """
    Email max 1× denně:
      - pokud už dnes šel email, nic neposíláme
      - posíláme plain text (stabilní)
    """
    enabled = (os.getenv("EMAIL_ENABLED", "false").lower().strip() == "true")
    if not enabled:
        return

    sender = (os.getenv("EMAIL_SENDER") or "").strip()
    receiver = (os.getenv("EMAIL_RECEIVER") or "").strip()
    pwd = (os.getenv("GMAILPASSWORD") or "").strip()
    if not (sender and receiver and pwd):
        print("⚠️ Email zapnutý, ale chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")
        return

    state_dir = cfg.state_dir or ".state"
    os.makedirs(state_dir, exist_ok=True)
    last_email_file = os.path.join(state_dir, "last_email_date.txt")

    day = now.strftime("%Y-%m-%d")
    last = _read_text(last_email_file, "")
    if last == day:
        return

    # payload
    if isinstance(snapshot_or_payload, dict) and snapshot_or_payload.get("kind") == "weekly_earnings":
        subject = f"EARNINGS – týdenní přehled ({day})"
        body = snapshot_or_payload.get("text", "")
    else:
        reason = ""
        try:
            reason = snapshot_or_payload.get("meta", {}).get("reason", "")
        except Exception:
            reason = ""
        subject = f"MEGA INVESTIČNÍ RADAR – {reason.upper() or tag.upper()} ({day})"
        # formátovaný report už se posílá přes telegram – tady pošli to stejné, co už caller poslal do telegramu
        # caller nám ale report text neposílá vždy => fallback “nic”
        body = ""
        try:
            # pokud caller posílá přímo snapshot, report text si vytvoříme až v callerovi; tady necháme prázdné
            body = snapshot_or_payload.get("rendered_text", "") or ""
        except Exception:
            body = ""
        if not body:
            # nejhorší fallback: pošli aspoň hlavičku
            body = f"{subject}\n\n(Tip: pro email posílej do maybe_send_email_report payload s klíčem rendered_text.)"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=40)
        server.ehlo()
        server.starttls()
        server.login(sender, pwd)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        _write_text(last_email_file, day)
        print("✅ Email OK")
    except Exception as e:
        print("❌ Email ERROR:", repr(e))