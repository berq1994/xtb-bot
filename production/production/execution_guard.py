from __future__ import annotations

from typing import Any, Dict, List


def build_execution_guard(
    alerts: List[Dict[str, Any]],
    decision: Dict[str, Any] | None = None,
    risk_overlay: Dict[str, Any] | None = None,
    performance_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    decision = decision or {}
    risk_overlay = risk_overlay or {}
    performance_summary = performance_summary or {}

    blocked_reasons: List[str] = []
    guardrails: List[str] = []

    recommended_mode = str(decision.get("recommended_mode", "NORMAL"))
    risk_posture = str(risk_overlay.get("risk_posture", "NORMAL"))
    max_new_positions = int(risk_overlay.get("max_new_positions", decision.get("max_new_positions", 0)) or 0)
    overall_hit_rate = float(performance_summary.get("overall_hit_rate", 0.0) or 0.0)
    scored_records = int(performance_summary.get("scored_records", 0) or 0)

    if risk_overlay.get("kill_switch_armed"):
        blocked_reasons.append("Kill switch je aktivní kvůli slabé historické výkonnosti alertů.")
    if risk_overlay.get("macro_lock"):
        guardrails.append("Makro lock: nové vstupy pouze po potvrzení price action.")
    if risk_overlay.get("earnings_lock"):
        guardrails.append("Earnings lock: neotvírat plné size přes close bez výjimečného důvodu.")
    if not risk_overlay.get("allow_overnight", True):
        guardrails.append("No overnight: nechat pouze intradenní nebo potvrzené setupy.")
    if recommended_mode in {"CAUTIOUS", "DEFENSIVE"}:
        guardrails.append(f"Režim {recommended_mode}: vstupy jen manuálně a selektivně.")

    require_price_action_confirmation = True
    allow_new_risk = max_new_positions > 0 and not blocked_reasons

    if scored_records >= 10 and overall_hit_rate >= 0.58 and risk_posture not in {"LOCK NEW RISK", "TIGHT"}:
        guard_status = "SELECTIVE_MANUAL"
    elif blocked_reasons:
        guard_status = "BLOCK_NEW_RISK"
        allow_new_risk = False
    elif risk_posture in {"TIGHT", "REDUCE SIZE"}:
        guard_status = "CONFIRM_ONLY"
    else:
        guard_status = "MANUAL_ONLY"

    approved_alerts: List[Dict[str, Any]] = []
    blocked_alerts: List[Dict[str, Any]] = []
    for item in alerts:
        priority = str(item.get("priority", "LOW")).upper()
        status = str(item.get("status", "WATCHLIST")).upper()
        approved = allow_new_risk and priority in {"HIGH", "MEDIUM"} and status not in {"NO TRADE"}
        record = {
            "category": item.get("category"),
            "title": item.get("title"),
            "priority": priority,
            "status": status,
        }
        if approved:
            approved_alerts.append(record)
        else:
            blocked_alerts.append(record)

    if not guardrails:
        guardrails.append("Všechny vstupy zůstávají manuální. Požaduj potvrzení price action a objemu.")

    return {
        "guard_status": guard_status,
        "allow_new_risk": allow_new_risk,
        "require_price_action_confirmation": require_price_action_confirmation,
        "max_new_positions": max_new_positions if allow_new_risk else 0,
        "blocked_reasons": blocked_reasons,
        "guardrails": guardrails,
        "approved_alert_count": len(approved_alerts),
        "blocked_alert_count": len(blocked_alerts),
        "approved_alerts": approved_alerts[:5],
        "blocked_alerts": blocked_alerts[:5],
    }
