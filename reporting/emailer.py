# reporting/emailer.py
from __future__ import annotations

import os
import math
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Any, Dict, List, Optional


# ============================================================
# Helpers
# ============================================================

def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    if v == "":
        return default
    return v in ("1", "true", "yes", "y", "on")


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def fmt_pct(val: Any) -> str:
    f = _safe_float(val)
    if f is None:
        return "—"
    return f"{f:+.2f}%"


def fmt_num(val: Any, nd: int = 2) -> str:
    f = _safe_float(val)
    if f is None:
        return "—"
    return f"{f:.{nd}f}"


def fmt_x(val: Any, nd: int = 2) -> str:
    f = _safe_float(val)
    if f is None:
        return "—"
    return f"{f:.{nd}f}×"


def fmt_str(val: Any) -> str:
    s = ("" if val is None else str(val)).strip()
    return s if s else "—"


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )


# ============================================================
# Email build
# ============================================================

def _build_subject(now: datetime, title: str = "MEGA INVESTIČNÍ RADAR") -> str:
    return f"{title} | {now.strftime('%Y-%m-%d %H:%M')}"


def _build_text_report(payload: Dict[str, Any]) -> str:
    now = payload.get("now")
    regime = payload.get("regime_label")
    regime_detail = payload.get("regime_detail")
    top = payload.get("top", []) or []
    weak = payload.get("weak", []) or []

    lines: List[str] = []
    lines.append(f"📡 MEGA INVESTIČNÍ RADAR ({fmt_str(now)})")
    lines.append(f"Režim trhu: {fmt_str(regime)} | {fmt_str(regime_detail)}")
    lines.append("")

    if top:
        lines.append("🔥 TOP kandidáti:")
        for it in top:
            lines.append(
                f"- {fmt_str(it.get('ticker'))} | 1D: {fmt_pct(it.get('pct_1d'))} | "
                f"score: {fmt_num(it.get('score'))} | "
                f"RS(5D-SPY): {fmt_pct(it.get('rs_5d'))} | "
                f"vol: {fmt_x(it.get('vol_ratio'))} | src: {fmt_str(it.get('src'))}"
            )
            if it.get("movement"):
                lines.append(f"  pohyb: {fmt_str(it.get('movement'))}")
            if it.get("suggestion"):
                lines.append(f"  → {fmt_str(it.get('suggestion'))}")
            if it.get("why"):
                lines.append(f"  why: {fmt_str(it.get('why'))}")

            news = it.get("news") or []
            if news:
                for n in news[:3]:
                    lines.append(f"   • {fmt_str(n.get('src'))}: {fmt_str(n.get('title'))}")
                    if n.get("link"):
                        lines.append(f"     {n.get('link')}")
        lines.append("")

    if weak:
        lines.append("🧊 SLABÉ (kandidáti na redukci):")
        for it in weak:
            lines.append(
                f"- {fmt_str(it.get('ticker'))} | 1D: {fmt_pct(it.get('pct_1d'))} | "
                f"score: {fmt_num(it.get('score'))} | "
                f"RS(5D-SPY): {fmt_pct(it.get('rs_5d'))} | "
                f"vol: {fmt_x(it.get('vol_ratio'))} | src: {fmt_str(it.get('src'))}"
            )
            if it.get("movement"):
                lines.append(f"  pohyb: {fmt_str(it.get('movement'))}")
            if it.get("suggestion"):
                lines.append(f"  → {fmt_str(it.get('suggestion'))}")
            if it.get("why"):
                lines.append(f"  why: {fmt_str(it.get('why'))}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _build_html_report(payload: Dict[str, Any]) -> str:
    # jednoduché HTML, ať to Gmail nepřekope
    now = _html_escape(fmt_str(payload.get("now")))
    regime = _html_escape(fmt_str(payload.get("regime_label")))
    regime_detail = _html_escape(fmt_str(payload.get("regime_detail")))

    top = payload.get("top", []) or []
    weak = payload.get("weak", []) or []

    def row(it: Dict[str, Any]) -> str:
        ticker = _html_escape(fmt_str(it.get("ticker")))
        pct_1d = _html_escape(fmt_pct(it.get("pct_1d")))
        score = _html_escape(fmt_num(it.get("score")))
        rs_5d = _html_escape(fmt_pct(it.get("rs_5d")))
        vol = _html_escape(fmt_x(it.get("vol_ratio")))
        src = _html_escape(fmt_str(it.get("src")))
        movement = _html_escape(fmt_str(it.get("movement"))) if it.get("movement") else ""
        suggestion = _html_escape(fmt_str(it.get("suggestion"))) if it.get("suggestion") else ""
        why = _html_escape(fmt_str(it.get("why"))) if it.get("why") else ""

        news_html = ""
        news = it.get("news") or []
        if news:
            items = []
            for n in news[:3]:
                ns = _html_escape(fmt_str(n.get("src")))
                nt = _html_escape(fmt_str(n.get("title")))
                link = (n.get("link") or "").strip()
                if link:
                    link_esc = _html_escape(link)
                    items.append(f"<li><b>{ns}:</b> <a href=\"{link_esc}\">{nt}</a></li>")
                else:
                    items.append(f"<li><b>{ns}:</b> {nt}</li>")
            news_html = "<ul style='margin:6px 0 0 18px; padding:0;'>" + "".join(items) + "</ul>"

        extra = ""
        if movement or suggestion or why or news_html:
            extra_parts = []
            if movement:
                extra_parts.append(f"<div><b>Pohyb:</b> {movement}</div>")
            if suggestion:
                extra_parts.append(f"<div><b>→</b> {suggestion}</div>")
            if why:
                extra_parts.append(f"<div><b>Why:</b> {why}</div>")
            extra = "<div style='margin-top:6px; font-size: 13px; color:#222;'>" + "".join(extra_parts) + news_html + "</div>"

        return f"""
        <tr>
          <td style="padding:10px; border-bottom:1px solid #eee;">
            <div style="font-size:15px;"><b>{ticker}</b> <span style="color:#666;">({src})</span></div>
            <div style="margin-top:4px; color:#444;">
              <span><b>1D:</b> {pct_1d}</span> &nbsp; | &nbsp;
              <span><b>score:</b> {score}</span> &nbsp; | &nbsp;
              <span><b>RS:</b> {rs_5d}</span> &nbsp; | &nbsp;
              <span><b>vol:</b> {vol}</span>
            </div>
            {extra}
          </td>
        </tr>
        """

    top_rows = "".join(row(it) for it in top) if top else ""
    weak_rows = "".join(row(it) for it in weak) if weak else ""

    def section(title: str, rows: str) -> str:
        if not rows:
            return ""
        return f"""
        <h3 style="margin:18px 0 8px 0;">{_html_escape(title)}</h3>
        <table style="width:100%; border-collapse:collapse; background:#fff; border:1px solid #eee;">
          {rows}
        </table>
        """

    html = f"""
    <div style="font-family:Arial, Helvetica, sans-serif; background:#fafafa; padding:16px;">
      <div style="max-width:780px; margin:0 auto; background:#ffffff; border:1px solid #eee; border-radius:10px; overflow:hidden;">
        <div style="padding:16px 18px; border-bottom:1px solid #eee;">
          <div style="font-size:18px;"><b>📡 MEGA INVESTIČNÍ RADAR</b></div>
          <div style="margin-top:6px; color:#555;">{now}</div>
          <div style="margin-top:8px; color:#111;">
            <b>Režim trhu:</b> {regime} <span style="color:#666;">| {regime_detail}</span>
          </div>
        </div>

        <div style="padding:16px 18px;">
          {section("🔥 TOP kandidáti", top_rows)}
          {section("🧊 Slabé (kandidáti na redukci)", weak_rows)}
        </div>

        <div style="padding:12px 18px; border-top:1px solid #eee; color:#777; font-size:12px;">
          Tento report je analytický přehled (ne investiční doporučení). Vstupy vždy filtruj přes svůj plán a risk management.
        </div>
      </div>
    </div>
    """
    return html.strip()


# ============================================================
# Send email
# ============================================================

def send_email(subject: str, text_body: str, html_body: str) -> None:
    sender = (os.getenv("EMAIL_SENDER") or "").strip()
    receiver = (os.getenv("EMAIL_RECEIVER") or "").strip()
    password = (os.getenv("GMAILPASSWORD") or "").strip()

    if not sender or not receiver or not password:
        raise RuntimeError("Email není nastaven: chybí EMAIL_SENDER/EMAIL_RECEIVER/GMAILPASSWORD.")

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Gmail SMTP
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(sender, password)
        s.sendmail(sender, [receiver], msg.as_string())


def maybe_send_email_report(payload: Dict[str, Any]) -> bool:
    """
    payload očekává klíče:
      - now (string nebo datetime)
      - regime_label, regime_detail
      - top: list[dict]
      - weak: list[dict]
    """
    if not _env_bool("EMAIL_ENABLED", False):
        print("EMAIL_ENABLED=false -> email report se neposílá.")
        return False

    # “now” si znormalizujeme
    now = payload.get("now")
    if isinstance(now, datetime):
        now_dt = now
        payload = dict(payload)
        payload["now"] = now_dt.strftime("%Y-%m-%d %H:%M")
    else:
        now_dt = datetime.now()

    subject = _build_subject(now_dt)
    text_body = _build_text_report(payload)
    html_body = _build_html_report(payload)

    send_email(subject, text_body, html_body)
    print("✅ Email report odeslán.")
    return True