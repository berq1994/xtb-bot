from collections import Counter
from typing import Dict, List


CATEGORY_CAPS = {
    "geo": 2,
    "earnings": 3,
    "macro": 2,
    "corporate": 2,
}


def _ticker_penalty(tickers: List[str]) -> float:
    if not tickers:
        return 0.12
    if len(tickers) > 5:
        return 0.05
    return 0.0


def evaluate_alerts(alerts: List[Dict], governance_mode: str) -> Dict:
    reviewed = []
    approved_count = 0
    title_counts = Counter(str(item.get("title", "")).strip().lower() for item in alerts)
    category_seen: Counter[str] = Counter()

    for item in alerts:
        category = str(item.get("category", "unknown")).lower()
        title = str(item.get("title", "")).strip()
        impact = float(item.get("impact", 0.0) or 0.0)
        confidence = float(item.get("confidence", 0.0) or 0.0)
        relevance = float(item.get("relevance", impact) or impact)
        priority = str(item.get("priority", "LOW")).upper()
        score = (impact * 0.45) + (confidence * 0.35) + (relevance * 0.20)
        reasons = []

        if impact < 0.65:
            score -= 0.15
            reasons.append("Impact pod minimálním prahem")
        elif impact < 0.72:
            score -= 0.05
            reasons.append("Impact je jen hraniční")

        ticker_penalty = _ticker_penalty(item.get("tickers", []))
        if ticker_penalty:
            score -= ticker_penalty
            reasons.append("Ticker mapping je slabý")

        if title_counts[title.lower()] > 1:
            score -= 0.08
            reasons.append("Duplicitní téma")

        category_seen[category] += 1
        if category_seen[category] > CATEGORY_CAPS.get(category, 2):
            score -= 0.06
            reasons.append("Přesycená kategorie")

        if category == "earnings" and impact >= 0.78:
            score += 0.04
            reasons.append("Silný earnings event")
        if category == "macro" and priority in {"HIGH", "MEDIUM"}:
            score += 0.03
            reasons.append("Makro den zvyšuje význam volatility")

        if governance_mode == "SAFE_MODE" and priority == "LOW":
            score -= 0.10
            reasons.append("SAFE_MODE tlumí low-priority alert")

        final_score = round(max(0.0, min(1.0, score)), 2)
        approved = final_score >= 0.69 and impact >= 0.65 and bool(item.get("tickers"))
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
