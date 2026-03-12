from typing import Dict, List


def build_execution_guard(
    alerts: List[Dict],
    decision: Dict | None = None,
    risk_overlay: Dict | None = None,
    performance_summary: Dict | None = None,
) -> Dict:
    decision = decision or {}
    risk_overlay = risk_overlay or {}
    performance_summary = performance_summary or {}

    recommended_mode = str(decision.get("recommended_mode", "NORMAL")).upper()
    risk_posture = str(risk_overlay.get("risk_posture", "NORMAL")).upper()

    allow_new_risk = True
    require_price_action_confirmation = True
    guard_status = "MANUAL_ONLY"
    guardrails: List[str] = []
    blocked_reasons: List[str] = []

    if risk_posture == "LOCK NEW RISK":
        allow_new_risk = False
        guard_status = "BLOCK_NEW_RISK"
        blocked_reasons.append("Risk posture blokuje nové risk vstupy.")
    elif risk_overlay.get("macro_lock"):
        allow_new_risk = True
        guard_status = "CONFIRM_ONLY"
        blocked_reasons.append("Macro lock je aktivní, nové vstupy jen po potvrzení.")
    elif risk_overlay.get("earnings_lock") and recommended_mode in {"DEFENSIVE", "CAUTIOUS"}:
        allow_new_risk = True
        guard_status = "SELECTIVE_MANUAL"
        blocked_reasons.append("Earnings lock vyžaduje ruční selekci a menší size.")
    elif risk_posture == "TIGHT":
        allow_new_risk = True
        guard_status = "CONFIRM_ONLY"
        blocked_reasons.append("Nové vstupy jen s potvrzením price action.")
    elif risk_posture == "REDUCE SIZE" or recommended_mode == "SELECTIVE":
        allow_new_risk = True
        guard_status = "SELECTIVE_MANUAL"
    else:
        allow_new_risk = True
        guard_status = "MANUAL_ONLY"

    if performance_summary.get("overall_hit_rate", 0.0) < 0.45 and performance_summary.get("scored_records", 0) >= 6:
        guardrails.append("Nízký hit rate trackeru, preferovat jen nejsilnější setupy.")
    guardrails.append("Nevstupovat bez potvrzení price action.")
    guardrails.append("Respektovat max počet nových pozic a sektorovou koncentraci.")
    guardrails.append("Při headline volatilitě zmenšit size.")

    approved_alert_count = 0
    blocked_alert_count = 0

    for alert in alerts:
        status = str(alert.get("status", "")).upper()
        priority = str(alert.get("priority", "")).upper()
        impact = float(alert.get("impact", 0.0) or 0.0)

        if status in {"NO TRADE"}:
            blocked_alert_count += 1
            continue
        if priority == "LOW" and impact < 0.72:
            blocked_alert_count += 1
            continue
        approved_alert_count += 1

    max_new_positions = int(risk_overlay.get("max_new_positions", decision.get("max_new_positions", 0) or 0))

    return {
        "guard_status": guard_status,
        "allow_new_risk": allow_new_risk,
        "require_price_action_confirmation": require_price_action_confirmation,
        "guardrails": guardrails,
        "blocked_reasons": blocked_reasons,
        "approved_alert_count": approved_alert_count,
        "blocked_alert_count": blocked_alert_count,
        "max_new_positions": max_new_positions,
    }
