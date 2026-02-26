# reporting/emailer.py
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _env_bool(name: str, default: str = "false") -> bool:
    return (os.getenv(name, default).strip().lower() == "true")


def _send_email(sender: str, receiver: str, app_password: str, subject: str, body: str, png_paths=None):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for p in (png_paths or []):
        try:
            with open(p, "rb") as f:
                img = MIMEImage(f.read())
            img.add_header("Content-Disposition", "attachment", filename=os.path.basename(p))
            msg.attach(img)
        except Exception as e:
            print("⚠️ Email attachment error:", p, e)

    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=40)
    server.ehlo()
    server.starttls()
    server.login(sender, app_password)
    server.sendmail(sender, receiver, msg.as_string())
    server.quit()


def _make_png(snapshot: dict, out_path: str) -> str:
    """
    Vytvoří jednoduchý graf změny 1D pro TOP+WORST (aby byl vizuál v emailu).
    """
    if not isinstance(snapshot, dict) or "top" not in snapshot:
        return ""

    rows = []
    rows.extend(snapshot.get("top", []))
    rows.extend(snapshot.get("worst", []))

    labels = []
    vals = []
    for r in rows:
        p = r.get("pct_1d")
        if p is None:
            continue
        labels.append(r.get("ticker", "?"))
        vals.append(float(p))

    if not labels:
        return ""

    plt.figure(figsize=(10, 4))
    # bar colors: green for +, red for -
    colors = ["green" if v >= 0 else "red" for v in vals]
    plt.bar(labels, vals, color=colors)
    plt.axhline(0, linewidth=1)
    plt.title("Změna ceny 1D (TOP + SLABÉ)")
    plt.ylabel("%")
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()
    return out_path


def maybe_send_email_report(cfg, snapshot: dict, now: datetime, tag: str = "premarket"):
    """
    Pravidlo: EMAIL max 1× denně.
    Ovládání přes env:
      EMAIL_ENABLED=true
      EMAIL_SENDER, EMAIL_RECEIVER, GMAILPASSWORD
    """
    enabled = _env_bool("EMAIL_ENABLED", "false")
    if not enabled:
        return

    sender = (os.getenv("EMAIL_SENDER") or "").strip()
    receiver = (os.getenv("EMAIL_RECEIVER") or "").strip()
    app_pass = (os.getenv("GMAILPASSWORD") or "").strip()

    if not sender or not receiver or not app_pass:
        print("⚠️ Email zapnutý, ale chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")
        return

    # dedupe 1× denně přes .state/last_email_day.txt
    state_dir = getattr(cfg, "state_dir", ".state") if cfg else ".state"
    os.makedirs(state_dir, exist_ok=True)
    last_file = os.path.join(state_dir, "last_email_day.txt")

    day = now.strftime("%Y-%m-%d")
    last = ""
    try:
        if os.path.exists(last_file):
            with open(last_file, "r", encoding="utf-8") as f:
                last = f.read().strip()
    except Exception:
        last = ""

    if last == day:
        return

    # body text
    if isinstance(snapshot, dict) and snapshot.get("kind") == "weekly_earnings":
        body = snapshot.get("text", "")
        subject = f"Earnings – týdenní tabulka ({day})"
        png_paths = []
    else:
        subject = f"MEGA INVESTIČNÍ RADAR – {tag.upper()} ({day})"
        # pokud report text generuje formatter, přijde sem jako snapshot dict -> uděláme z něj krátký text
        body = "Report je v Telegramu.\n\n(Email = 1× denně. Pokud chceš, můžeme sem posílat i plný text.)"
        png_paths = []
        try:
            out_png = os.path.join(state_dir, f"report_{day}.png")
            p = _make_png(snapshot, out_png)
            if p:
                png_paths = [p]
        except Exception as e:
            print("⚠️ PNG generation error:", e)

    try:
        _send_email(sender, receiver, app_pass, subject, body, png_paths=png_paths)
        with open(last_file, "w", encoding="utf-8") as f:
            f.write(day)
        print("✅ Email OK (odesláno)")
    except Exception as e:
        print("❌ Email ERROR:", repr(e))