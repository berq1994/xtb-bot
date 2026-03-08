import json
from pathlib import Path

from production.alert_evaluator import evaluate_alerts
from production.critic import review_alerts
from production.decision_engine import build_decision_overlay
from production.file_inputs import read_text_or_default
from production.governance_bridge import extract_governance_mode, read_governance_snapshot
from production.history_store import archive_run
from production.message_enhancer import (
    parse_alert_lines,
    parse_briefing_items,
    render_alerts_message,
    render_briefing_message,
)
from production.outcome_tracker import register_alerts
from production.performance_tracker import summarize_performance
from production.report_builder import build_production_report, render_production_report
from production.telegram_http import send_telegram_http


def run_daily_flow(logger=None):
    briefing_text = read_text_or_default("telegram_briefing.txt", "Briefing zatím není.")
    alerts_text = read_text_or_default("telegram_alerts.txt", "")
    ticket_text = read_text_or_default("xtb_manual_ticket.txt", "Ticket zatím není.")
    journal_text = read_text_or_default("xtb_trade_journal.txt", "Journal zatím není.")
    alert_lines = [x for x in alerts_text.splitlines() if x.strip()]

    gov_snapshot = read_governance_snapshot()
    governance_mode = extract_governance_mode(gov_snapshot)

    steps = [
        "inputs_loaded",
        "governance_checked",
        "briefing_ready",
        "alerts_ready",
        "ticket_ready",
        "journal_ready",
    ]

    if logger:
        logger.info(f"governance mode: {governance_mode}")
        logger.info(f"alerts prepared: {len(alert_lines)}")

    briefing_items = parse_briefing_items(briefing_text)
    parsed_alerts = parse_alert_lines(alert_lines)
    evaluation = evaluate_alerts(parsed_alerts, governance_mode)
    critic = review_alerts(parsed_alerts)
    decision = build_decision_overlay(briefing_items, parsed_alerts, evaluation)
    tracker_summary = register_alerts(parsed_alerts)
    performance_summary = summarize_performance()

    briefing_message = render_briefing_message(
        briefing_text,
        briefing_items,
        decision=decision,
        critic_summary=critic,
        tracker_summary=tracker_summary,
    )
    alerts_message = render_alerts_message(
        parsed_alerts,
        critic_summary=critic,
        tracker_summary=performance_summary,
    )

    brief_delivery = send_telegram_http(briefing_message)
    alerts_delivery = send_telegram_http(alerts_message)

    steps.extend(
        [
            "alerts_evaluated",
            "critic_reviewed",
            "decision_overlay_ready",
            "outcome_registry_updated",
            "performance_summary_updated",
            "telegram_briefing_sent" if brief_delivery.get("delivered") else "telegram_briefing_not_sent",
            "telegram_alerts_sent" if alerts_delivery.get("delivered") else "telegram_alerts_not_sent",
        ]
    )

    payload = build_production_report(
        steps=steps,
        briefing_text=briefing_message,
        alert_lines=alert_lines,
        ticket_text=ticket_text,
        journal_text=journal_text,
        governance_mode=governance_mode,
    )

    out = {
        "report": payload,
        "telegram_briefing": brief_delivery,
        "telegram_alerts": alerts_delivery,
        "evaluation": evaluation,
        "critic": critic,
        "decision": decision,
        "registry_summary": tracker_summary,
        "performance_summary": performance_summary,
        "briefing_items": briefing_items,
        "parsed_alerts": parsed_alerts,
    }
    out["metrics"] = archive_run(
        out,
        parsed_alerts,
        briefing_items,
        evaluation,
        critic=critic,
        decision=decision,
        tracker_summary=tracker_summary,
        performance_summary=performance_summary,
    )

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block14_production_run.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("production_report.txt").write_text(render_production_report(payload), encoding="utf-8")
    return out
