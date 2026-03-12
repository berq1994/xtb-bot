def compute_quality_score(has_price=True, has_volume=True, source_ok=True, stale=False, mapped=True):
    score = 100
    if not has_price:
        score -= 45
    if not has_volume:
        score -= 15
    if not source_ok:
        score -= 20
    if stale:
        score -= 10
    if not mapped:
        score -= 10
    return max(0, min(100, score))

def quality_label(score: int) -> str:
    if score >= 85:
        return "HIGH"
    if score >= 65:
        return "MEDIUM"
    return "LOW"
