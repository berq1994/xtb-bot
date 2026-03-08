from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def build_risk_overlay(
    briefing_items: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
    decision: Dict[str, Any] | None = None,
    performance_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    decision = decision or {}
    performance_summary = performance_summary or {}

    categories = Counter(str(x.get("category", "unknown")).lower() for x in alerts)
    statuses = Counter(str(x.get("status", "unknown")).upper() for x in alerts)
    priorities = Counter(str(x.get("priority", "unknown")).upper() for x in alerts)

    macro_lock = categories.get("macro", 0) > 0 and statuses.get("NO TRADE", 0) > 0
    earnings_lock = categories.get("earnings", 0) > 0
    geo_vol = categories.get("geo", 0) > 0 and statuses.get("HIGH VOL", 0) > 0
    setup_forming = statuses.get("SETUP FORMING", 0)
    high_priority = priorities.get("HIGH", 0)
    medium_priority = priorities.get("MEDIUM", 0)

    overall_hit_rate = float(performance_summary.get("overall_hit_rate", 0.0) or 0.0)
    pending_records = int(performance_summary.get("pending_records", 0) or 0)
    scored_records = int(performance_summary.get("scored_records", 0) or 0)

    risk_posture = "NORMAL"
    max_single_position_risk_pct = 0.50
    max_sector_exposure_pct = 35
    allow_overnight = True
    kill_switch_armed = False
    max_new_positions = int(decision.get("max_new_positions", 2) or 2)
    portfolio_actions: List[str] = []

    if macro_lock:
        risk_posture = "REDUCE SIZE"
        max_single_position_risk_pct = 0.35
        allow_overnight = False
        portfolio_actions.append("Makro event drží trh v risk-on/risk-off režimu. Nové vstupy jen po potvrzení.")

    if earnings_lock:
        max_single_position_risk_pct = min(max_single_position_risk_pct, 0.35)
        allow_overnight = False
        portfolio_actions.append("Earnings témata: nebrat plnou velikost a chránit se proti gap risku.")

    if geo_vol:
        max_sector_exposure_pct = min(max_sector_exposure_pct, 25)
        portfolio_actions.append("Geo headline risk: hlídat koncentraci v energiích a dopravě.")

    if high_priority >= 2 or setup_forming >= 2:
        risk_posture = "TIGHT"
        max_new_positions = min(max_new_positions, 1)
        max_single_position_risk_pct = min(max_single_position_risk_pct, 0.30)
        max_sector_exposure_pct = min(max_sector_exposure_pct, 25)
        portfolio_actions.append("Více silných témat současně. Preferovat jen nejlepší setup dne.")

    if scored_records >= 10 and overall_hit_rate < 0.45:
        risk_posture = "LOCK NEW RISK"
        kill_switch_armed = True
        allow_overnight = False
        max_new_positions = 0
        max_single_position_risk_pct = 0.0
        max_sector_exposure_pct = 0
        portfolio_actions.append("Historická hit-rate je slabá. Pozastavit nové riskantní vstupy.")

    if pending_records > max(10, scored_records * 2) and medium_priority >= 2:
        portfolio_actions.append("Tracker má hodně nevyhodnocených záznamů. Brát nové signály opatrněji.")

    if not portfolio_actions:
        portfolio_actions.append("Riziko je pod kontrolou. Držet selektivní vstupy a potvrzení price action.")

    return {
        "risk_posture": risk_posture,
        "max_single_position_risk_pct": round(max_single_position_risk_pct, 2),
        "max_sector_exposure_pct": int(max_sector_exposure_pct),
        "allow_overnight": allow_overnight,
        "earnings_lock": earnings_lock,
        "macro_lock": macro_lock,
        "kill_switch_armed": kill_switch_armed,
        "max_new_positions": max_new_positions,
        "portfolio_actions": portfolio_actions,
        "summary": {
            "categories": dict(categories),
            "statuses": dict(statuses),
            "priorities": dict(priorities),
        },
    }
