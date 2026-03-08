def relevance_score(urgency: float, source_quality: float, direct_market_link: float):
    score = float(urgency) * 0.4 + float(source_quality) * 0.35 + float(direct_market_link) * 0.25
    return round(min(1.0, max(0.0, score)), 3)
