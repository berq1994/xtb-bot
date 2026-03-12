def relevance_score(urgency: float, source_quality: float, market_link: float):
    score = float(urgency) * 0.4 + float(source_quality) * 0.35 + float(market_link) * 0.25
    return round(min(1.0, max(0.0, score)), 3)

def impact_score(severity: float, breadth: float, duration: float):
    score = float(severity) * 0.45 + float(breadth) * 0.30 + float(duration) * 0.25
    return round(min(1.0, max(0.0, score)), 3)
