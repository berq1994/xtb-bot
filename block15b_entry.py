import json
from pathlib import Path
from delivery_autonomous.file_inputs import read_text_or_default
from delivery_autonomous.telegram_payload import build_telegram_payload
from delivery_autonomous.email_payload import build_email_payload
from delivery_autonomous.telegram_transport import send_telegram_payload
from delivery_autonomous.email_transport import send_email_payload
from delivery_autonomous.delivery_log import log_delivery
from delivery_autonomous.report_builder import build_delivery_report

def main():
    briefing = read_text_or_default("autonomous_briefing.txt", "Autonomous briefing zatím není.")
    alerts = read_text_or_default("autonomous_alerts.txt", "Autonomous alerts zatím nejsou.")
    handoff = read_text_or_default("autonomous_xtb_handoff.txt", "Autonomous handoff zatím není.")

    telegram_payload = build_telegram_payload(briefing, alerts, handoff)
    email_payload = build_email_payload("[XTB Bot]", briefing, alerts, handoff)

    telegram_result = send_telegram_payload(telegram_payload)
    email_result = send_email_payload(email_payload)

    report = build_delivery_report(
        telegram_result=telegram_result,
        email_result=email_result,
        briefing_len=len(briefing),
        alerts_len=len(alerts),
        handoff_len=len(handoff),
    )

    payload = {
        "telegram_result": telegram_result,
        "email_result": email_result,
        "telegram_payload_preview": telegram_payload[:1000],
        "email_payload": email_payload,
        "report": report,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block15b_delivery.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block15b_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("autonomous_delivery_report.txt").write_text(report, encoding="utf-8")
    Path("autonomous_email_payload.txt").write_text(json.dumps(email_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("autonomous_telegram_payload.txt").write_text(telegram_payload, encoding="utf-8")

    log_delivery({
        "telegram_result": telegram_result,
        "email_result": email_result,
    })

    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

