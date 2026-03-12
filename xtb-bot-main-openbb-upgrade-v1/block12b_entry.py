import json
from pathlib import Path
from delivery.alert_formatter import format_alerts
from delivery.briefing_formatter import format_briefing
from delivery.delivery_queue import enqueue
from telegram_layer.briefing_delivery import deliver_briefing
from telegram_layer.alert_delivery import deliver_alerts
from telegram_layer.command_router import route_command

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    b12a = _read_json(".state/block12a_live_intelligence.json", {"rows": [], "briefing": {}})
    rows = b12a.get("rows", [])
    briefing = b12a.get("briefing", {})

    briefing_text = format_briefing(briefing)
    alert_lines = format_alerts(rows)

    q1 = enqueue("briefing", briefing_text)
    q2 = enqueue("alerts", "\n".join(alert_lines))

    telegram_briefing = deliver_briefing(briefing_text)
    telegram_alerts = deliver_alerts(alert_lines)

    commands = [
        route_command("/briefing"),
        route_command("/alerts"),
        route_command("/watchlist"),
        route_command("/ticket"),
        route_command("/journal"),
    ]

    payload = {
        "briefing_text": briefing_text,
        "alert_lines": alert_lines,
        "delivery_queue_size": len(q2),
        "telegram_briefing": telegram_briefing,
        "telegram_alerts": telegram_alerts,
        "command_routes": commands,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block12b_delivery.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block12b_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("telegram_briefing.txt").write_text(briefing_text, encoding="utf-8")
    Path("telegram_alerts.txt").write_text("\n".join(alert_lines), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
