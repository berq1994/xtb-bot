from __future__ import annotations

from pathlib import Path


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def run_telegram_preview(payload=None) -> str:
    if not isinstance(payload, dict):
        payload = {}

    supervisor = _safe_dict(payload.get("supervisor"))
    ticket = _safe_dict(payload.get("ticket"))
    snapshot = _safe_dict(payload.get("snapshot"))

    regime = payload.get("regime", supervisor.get("regime", "mixed"))
    decision = payload.get("decision", supervisor.get("decision", "watch"))

    lead = _safe_dict(supervisor.get("leader")) or _safe_dict(snapshot.get("leader"))
    weak = _safe_dict(supervisor.get("laggard")) or _safe_dict(snapshot.get("laggard"))

    lines = []
    lines.append("Denní přehled trhu")
    lines.append(f"Režim: {regime}")
    lines.append(f"Rozhodnutí: {decision}")

    if lead:
        lines.append(
            f"Lead: {lead.get('symbol', '-')} | {lead.get('change_pct', 0)}% | trend {lead.get('trend', '-')} | zprávy {lead.get('sentiment_label', '-')}"
        )

    if weak:
        lines.append(
            f"Slabý: {weak.get('symbol', '-')} | {weak.get('change_pct', 0)}% | trend {weak.get('trend', '-')} | zprávy {weak.get('sentiment_label', '-')}"
        )

    lines.append("")
    lines.append("Ruční XTB ticket")
    lines.append(f"Symbol: {ticket.get('symbol', '-')}")
    lines.append(f"Směr: {ticket.get('direction', '-')}")
    lines.append(f"Vstup: {ticket.get('entry', '-')}")
    lines.append(f"SL: {ticket.get('stop_loss', '-')}")
    lines.append(f"TP: {ticket.get('take_profit', '-')}")
    lines.append(f"Sentiment: {ticket.get('news_sentiment', '-')}")

    lines.append("")
    lines.append("Kontrolní seznam:")
    checklist = ticket.get("checklist", [])
    if isinstance(checklist, list) and checklist:
        for item in checklist:
            lines.append(f"- {item}")
    else:
        lines.append("- Potvrdit graf v XTB")
        lines.append("- Potvrdit spread a volatilitu")
        lines.append("- Vstoupit jen po potvrzení")

    output = "\n".join(lines)
    Path("telegram_preview.txt").write_text(output, encoding="utf-8")
    return output