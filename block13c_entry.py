import json
from pathlib import Path
from orchestration.daily_runner import build_daily_orchestration
from orchestration.report_renderer import render_orchestration_report

def _read_text(path_str, default):
    path = Path(path_str)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    return default

def main():
    briefing_text = _read_text("telegram_briefing.txt", "Briefing zatím není.")
    ticket_text = _read_text("xtb_manual_ticket.txt", "Ticket zatím není.")
    journal_text = _read_text("xtb_trade_journal.txt", "Journal zatím není.")
    alerts_text = _read_text("telegram_alerts.txt", "")
    alert_lines = [x for x in alerts_text.splitlines() if x.strip()]

    payload = build_daily_orchestration(
        briefing_text=briefing_text,
        alert_lines=alert_lines,
        ticket_text=ticket_text,
        journal_note=journal_text,
    )
    rendered = render_orchestration_report(payload)

    out = {
        "orchestration": payload,
        "report_text": rendered,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block13c_daily_orchestration.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block13c_output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("daily_orchestration_report.txt").write_text(rendered, encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

