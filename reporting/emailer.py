import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import List, Optional
from datetime import datetime

from radar.config import RadarConfig
from reporting.charts import make_price_chart


def _send_email(cfg: RadarConfig, subject: str, body: str, image_paths: Optional[List[str]] = None):
    if not cfg.email_enabled:
        return
    if not (cfg.email_sender and cfg.email_receiver and cfg.gmail_password):
        print("⚠️ Email zapnutý, ale chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")
        return

    msg = MIMEMultipart()
    msg["From"] = cfg.email_sender
    msg["To"] = cfg.email_receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for p in (image_paths or []):
        try:
            with open(p, "rb") as f:
                img = MIMEImage(f.read())
            img.add_header("Content-Disposition", "attachment", filename=p.split("/")[-1])
            msg.attach(img)
        except Exception as e:
            print("⚠️ Email příloha chyba:", p, e)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=40)
        server.ehlo()
        server.starttls()
        server.login(cfg.email_sender, cfg.gmail_password)
        server.sendmail(cfg.email_sender, cfg.email_receiver, msg.as_string())
        server.quit()
        print("✅ Email OK: odesláno")
    except Exception as e:
        print("❌ Email ERROR:", repr(e))


def maybe_send_email_report(cfg: RadarConfig, snapshot: dict, now: datetime, tag: str):
    """
    Posíláme email jen když je email_enabled a jen 1× denně (ty chceš max 1×).
    Tady to voláme jen z 12:00 reportu.
    """
    if not cfg.email_enabled:
        return

    subject = f"MEGA INVESTIČNÍ RADAR – {now.strftime('%d.%m.%Y %H:%M')} ({tag})"
    lines = []
    meta = snapshot.get("meta", {})
    regime = meta.get("market_regime", {})
    lines.append(f"Čas: {meta.get('timestamp')}")
    lines.append(f"Režim trhu: {regime.get('label')} | {regime.get('detail')}")
    lines.append("")
    lines.append("TOP kandidáti:")
    for it in snapshot.get("top", []):
        lines.append(f"- {it['ticker']} ({it['resolved']}): {it.get('pct_1d') and f'{it['pct_1d']:+.2f}%' or '—'} | score {it['score']:.2f}")
        lines.append(f"  {it['advice']}")
        lines.append(f"  why: {it['why']}")
    lines.append("")
    lines.append("SLABÉ (kandidáti na redukci):")
    for it in snapshot.get("worst", []):
        lines.append(f"- {it['ticker']} ({it['resolved']}): {it.get('pct_1d') and f'{it['pct_1d']:+.2f}%' or '—'} | score {it['score']:.2f}")
        lines.append(f"  {it['advice']}")
        lines.append(f"  why: {it['why']}")

    # grafy pro TOP (max 3, ať email není obří)
    img_paths = []
    for it in snapshot.get("top", [])[:3]:
        p = make_price_chart(it["resolved"], days=30, out_dir=cfg.state_dir)
        if p:
            img_paths.append(p)

    _send_email(cfg, subject, "\n".join(lines), img_paths)