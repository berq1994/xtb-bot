import json
from pathlib import Path
from real_delivery.file_inputs import read_text_or_default
from real_delivery.telegram_live import send_telegram_live
from real_delivery.email_live import send_email_live
from real_delivery.reporting import render_delivery_report

def main():
    briefing = read_text_or_default("autonomous_briefing.txt", "Autonomous briefing zatím není.")
    alerts = read_text_or_default("autonomous_alerts.txt", "Autonomous alerts zatím nejsou.")
    handoff = read_text_or_default("autonomous_xtb_handoff.txt", "Autonomous handoff zatím není.")

    telegram_text = "

".join(["AUTONOMOUS DELIVERY", briefing[:1200], alerts[:1000], handoff[:1000]])[:4096]
    email_subject = "[XTB Bot] Real Delivery"
    email_body = "

".join([briefing, alerts, handoff])

    telegram = send_telegram_live(telegram_text)
    email = send_email_live(email_subject, email_body)

    payload = {
        "telegram": telegram,
        "email": email,
        "briefing_length": len(briefing),
        "alerts_length": len(alerts),
        "handoff_length": len(handoff),
    }

    report = render_delivery_report(payload)

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block16a_real_delivery.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block16a_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("real_delivery_report.txt").write_text(report, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

