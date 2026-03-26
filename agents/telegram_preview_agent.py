from __future__ import annotations

from pathlib import Path

RESEARCH_PATH = Path("research_live_report.txt")
THESIS_PATH = Path("thesis_updates.txt")


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _parse_key_values(path: str) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    data: dict[str, str] = {}
    for raw in file_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _read_research_highlights(limit: int = 2) -> list[str]:
    highlights: list[str] = []
    if RESEARCH_PATH.exists():
        for raw in RESEARCH_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("-"):
                highlights.append(line)
            if len(highlights) >= limit:
                break
    return highlights


def _read_thesis_lines(limit: int = 2) -> list[str]:
    picks: list[str] = []
    if THESIS_PATH.exists():
        for raw in THESIS_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("-"):
                picks.append(line)
            if len(picks) >= limit:
                break
    return picks


def _build_from_generated_files() -> dict:
    ticket_map = _parse_key_values("xtb_manual_ticket.txt")
    supervisor_map = _parse_key_values("daily_briefing.txt")

    regime = ticket_map.get("Režim trhu") or supervisor_map.get("Režim trhu") or "mixed"
    decision = supervisor_map.get("Rozhodnutí") or "watch"

    ticket = {
        "symbol": ticket_map.get("Symbol", "-"),
        "direction": ticket_map.get("Směr", "-"),
        "entry": ticket_map.get("Vstupní reference", "-"),
        "stop_loss": ticket_map.get("Stop loss", "-"),
        "take_profit": ticket_map.get("Take profit", "-"),
        "news_sentiment": ticket_map.get("Sentiment zpráv", ticket_map.get("Sentiment", "-")),
        "checklist": [
            "Potvrdit graf v XTB",
            "Potvrdit spread a volatilitu",
            "Vstoupit jen po potvrzení",
        ],
    }

    return {
        "regime": regime,
        "decision": decision,
        "ticket": ticket,
        "research_highlights": _read_research_highlights(),
        "thesis_lines": _read_thesis_lines(),
    }


def run_telegram_preview(payload=None) -> str:
    if not isinstance(payload, dict):
        payload = _build_from_generated_files()

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

    research_highlights = payload.get("research_highlights", [])
    thesis_lines = payload.get("thesis_lines", [])
    if isinstance(research_highlights, list) and research_highlights:
        lines.append("")
        lines.append("Live research:")
        for item in research_highlights[:2]:
            lines.append(item)
    if isinstance(thesis_lines, list) and thesis_lines:
        lines.append("")
        lines.append("Thesis update:")
        for item in thesis_lines[:2]:
            lines.append(item)

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
