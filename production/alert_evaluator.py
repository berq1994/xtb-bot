from typing import List, Dict


def evaluate_alerts(alerts: List[Dict], governance_mode: str) -> Dict:
    reviewed = []
    approved_count = 0

    for item in alerts:
        score = item.get("confidence", 0.0)
        reasons = []
        if item.get("impact", 0.0) < 0.67:
            score -= 0.10
            reasons.append("Nízký impact")
        if len(item.get("tickers", [])) == 0:
            score -= 0.10
            reasons.append("Chybí tickery")
        if governance_mode == "SAFE_MODE" and item.get("priority") == "LOW":
            score -= 0.10
            reasons.append("SAFE_MODE tlumí low-priority alert")

        final_score = round(max(0.0, min(1.0, score)), 2)
        approved = final_score >= 0.70
        if approved:
            approved_count += 1
        reviewed.append(
            {
                "category": item.get("category"),
                "title": item.get("title"),
                "priority": item.get("priority"),
                "score": final_score,
                "approved": approved,
                "reasons": reasons or ["OK"],
            }
        )

    return {
        "approved_count": approved_count,
        "rejected_count": max(0, len(reviewed) - approved_count),
        "reviews": reviewed,
    }
