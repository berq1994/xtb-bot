from typing import Dict, List


def build_decision_overlay(briefing_items: List[Dict], alerts: List[Dict], evaluation: Dict) -> Dict:
    high_count = sum(1 for x in briefing_items if x.get("priority") == "HIGH") + sum(1 for x in alerts if x.get("priority") == "HIGH")
    medium_count = sum(1 for x in briefing_items if x.get("priority") == "MEDIUM") + sum(1 for x in alerts if x.get("priority") == "MEDIUM")
    rejected = int(evaluation.get("rejected_count", 0) or 0)
    approved = int(evaluation.get("approved_count", 0) or 0)

    if high_count >= 3:
        recommended_mode = "DEFENSIVE"
        max_new_positions = 1
        portfolio_note = "Více silných eventů najednou. Nové vstupy jen výjimečně a s menší velikostí."
    elif high_count >= 1 or medium_count >= 3:
        recommended_mode = "SELECTIVE"
        max_new_positions = 2
        portfolio_note = "Je aktivních víc témat. Preferovat jen čisté setupy s potvrzením."
    else:
        recommended_mode = "NORMAL"
        max_new_positions = 3
        portfolio_note = "Tok zpráv je zvládnutelný. Standardní selekce bez eskalace rizika."

    if rejected >= max(2, approved):
        recommended_mode = "CAUTIOUS"
        max_new_positions = min(max_new_positions, 1)
        portfolio_note = "Kvalita alertů je smíšená. Požaduj silnější potvrzení price action."

    return {
        "recommended_mode": recommended_mode,
        "max_new_positions": max_new_positions,
        "portfolio_note": portfolio_note,
    }
