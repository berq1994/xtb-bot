from typing import Dict, List


def build_risk_overlay(
    briefing_items: List[Dict],
    alerts: List[Dict],
    decision: Dict | None = None,
    performance_summary: Dict | None = None,
) -> Dict:
    decision = decision or {}
    performance_summary = performance_summary or {}

    combined = list(briefing_items) + list(alerts)
    high_vol = any(str(x.get("status", "")).upper() == "HIGH VOL" for x in combined)
    has_macro_no_trade = any(
        str(x.get("category", "")).lower() == "macro" and str(x.get("status", "")).upper() == "NO TRADE"
        for x in combined
    )
    has_earnings = any(str(x.get("category", "")).lower() == "earnings" for x in combined)

    scored_records = int(performance_summary.get("scored_records", 0) or 0)
    hit_rate = float(performance_summary.get("overall_hit_rate", 0.0) or 0.0)

    risk_posture = "NORMAL"
    max_single_position_risk_pct = 0.50
    max_sector_exposure_pct = 35
    allow_overnight = True
    earnings_lock = False
    macro_lock = False
    kill_switch_armed = False
    portfolio_actions: List[str] = []

    if high_vol:
        risk_posture = "REDUCE SIZE"
        max_single_position_risk_pct = 0.35
        portfolio_actions.append("Headline volatilita zvýšená, zmenšit size.")

    if has_earnings:
        earnings_lock = True
        allow_overnight = False
        portfolio_actions.append("Earnings risk: nepreferovat držení přes close bez extra důvodu.")

    if has_macro_no_trade:
        macro_lock = True
        risk_posture = "TIGHT"
        max_single_position_risk_pct = min(max_single_position_risk_pct, 0.25)
        portfolio_actions.append("Makro režim dne je citlivý, nové vstupy jen selektivně.")

    if scored_records >= 5 and hit_rate < 0.40:
        risk_posture = "LOCK NEW RISK"
        kill_switch_armed = True
        max_single_position_risk_pct = 0.0
        portfolio_actions.append("Tracker ukazuje slabý výkon, aktivovat obranný režim.")

    max_new_positions = int(decision.get("max_new_positions", 0) or 0)
    if risk_posture == "LOCK NEW RISK":
        max_new_positions = 0
    elif risk_posture == "TIGHT":
        max_new_positions = min(max_new_positions or 1, 1)

    return {
        "risk_posture": risk_posture,
        "max_single_position_risk_pct": max_single_position_risk_pct,
        "max_sector_exposure_pct": max_sector_exposure_pct,
        "allow_overnight": allow_overnight,
        "earnings_lock": earnings_lock,
        "macro_lock": macro_lock,
        "kill_switch_armed": kill_switch_armed,
        "max_new_positions": max_new_positions,
        "portfolio_actions": portfolio_actions,
    }
