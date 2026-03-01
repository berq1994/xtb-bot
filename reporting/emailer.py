# reporting/emailer.py
from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, List, Optional


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default


def _get_email_settings() -> Dict[str, str]:
    return {
        "enabled": (os.getenv("EMAIL_ENABLED") or "").strip(),
        "sender": (os.getenv("EMAIL_SENDER") or "").strip(),
        "receiver": (os.getenv("EMAIL_RECEIVER") or "").strip(),
        "password": (os.getenv("GMAILPASSWORD") or "").strip(),
        # volitelné:
        "smtp_host": (os.getenv("SMTP_HOST") or "smtp.gmail.com").strip(),
        "smtp_port": (os.getenv("SMTP_PORT") or "587").strip(),
    }


def _normalize_attachments(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Očekávané formáty:
      payload["attachments"] = [
        {"filename":"x.png", "content_type":"image/png", "data": b"..."},
        ...
      ]

    Fallback:
      payload["png_bytes"] = b"..."
      payload["png_filename"] = "chart.png"
    """
    atts: List[Dict[str, Any]] = []

    raw = payload.get("attachments")
    if isinstance(raw, list):
        for a in raw:
            if not isinstance(a, dict):
                continue
            fn = str(a.get("filename") or "").strip()
            ct = str(a.get("content_type") or "application/octet-stream").strip()
            data = a.get("data")
            if fn and isinstance(data, (bytes, bytearray)):
                atts.append({"filename": fn, "content_type": ct, "data": bytes(data)})

    # fallback single png
    if not atts:
        data = payload.get("png_bytes")
        if isinstance(data, (bytes, bytearray)):
            fn = str(payload.get("png_filename") or "chart.png").strip()
            atts.append({"filename": fn, "content_type": "image/png", "data": bytes(data)})

    return atts


def maybe_send_email_report(cfg, payload: Dict[str, Any], now: datetime, tag: str = "report") -> Dict[str, Any]:
    """
    Posílá email report, pokud EMAIL_ENABLED=true.

    payload:
      - rendered_text: str (tělo emailu)
      - subject: optional str
      - attachments: optional list of {filename, content_type, data(bytes)}
    """
    settings = _get_email_settings()

    enabled = _env_bool("EMAIL_ENABLED", default=False)
    if not enabled:
        return {"ok": False, "reason": "EMAIL_ENABLED not true"}

    sender = settings["sender"]
    receiver = settings["receiver"]
    password = settings["password"]
    smtp_host = settings["smtp_host"]
    try:
        smtp_port = int(settings["smtp_port"] or "587")
    except Exception:
        smtp_port = 587

    if not sender or not receiver or not password:
        return {"ok": False, "reason": "missing EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD"}

    text = str(payload.get("rendered_text") or "").strip()
    if not text:
        # fallback: něco minimálního
        text = "(report bez textu)"

    subject = str(payload.get("subject") or "").strip()
    if not subject:
        subject = f"[XTB Bot] {tag} — {now.strftime('%Y-%m-%d %H:%M')}"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.set_content(text)

    # attachments
    atts = _normalize_attachments(payload)
    for a in atts:
        fn = a["filename"]
        ct = a["content_type"]
        data = a["data"]

        # split content-type
        maintype = "application"
        subtype = "octet-stream"
        if "/" in ct:
            maintype, subtype = ct.split("/", 1)

        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=fn)

    # send
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=40) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.send_message(msg)

        return {"ok": True, "to": receiver, "attachments": len(atts)}
    except Exception as e:
        return {"ok": False, "reason": f"smtp_error: {type(e).__name__}: {e}"}