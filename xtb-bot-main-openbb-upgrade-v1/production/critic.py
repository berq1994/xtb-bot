from collections import Counter
from typing import Dict, List


def review_alerts(alerts: List[Dict]) -> Dict:
    reviews = []
    approved_count = 0
    title_counts = Counter(str(item.get("title", "")).strip().lower() for item in alerts)

    for item in alerts:
        score = float(item.get("confidence", 0.0) or 0.0)
        reasons = []
        title = str(item.get("title", "")).strip().lower()
        tickers = item.get("tickers") or []

        if not tickers:
            score -= 0.18
            reasons.append("Chybí tickery")
        if item.get("priority") == "LOW":
            score -= 0.10
            reasons.append("Low priority")
        if str(item.get("status", "")).upper() == "NO TRADE":
            score -= 0.06
            reasons.append("Status no-trade")
        risk_note = str(item.get("risk_note", ""))
        if "risk" not in risk_note.lower() and "riziko" not in risk_note.lower():
            score -= 0.05
            reasons.append("Slabá risk poznámka")
        if title_counts[title] > 1:
            score -= 0.08
            reasons.append("Duplicitní titulek")
        if any(not str(t).strip() for t in tickers):
            score -= 0.05
            reasons.append("Prázdný ticker")
        if float(item.get("confidence", 0.0) or 0.0) > 0.95 and float(item.get("impact", 0.0) or 0.0) < 0.75:
            score -= 0.07
            reasons.append("Confidence je neúměrně vysoké")

        final_score = round(max(0.0, min(1.0, score)), 2)
        approved = final_score >= 0.66 and bool(tickers)
        if approved:
            approved_count += 1
        reviews.append({
            "category": item.get("category"),
            "title": item.get("title"),
            "critic_score": final_score,
            "approved": approved,
            "reasons": reasons or ["OK"],
        })
    return {
        "approved_count": approved_count,
        "rejected_count": len(alerts) - approved_count,
        "reviews": reviews,
    }
