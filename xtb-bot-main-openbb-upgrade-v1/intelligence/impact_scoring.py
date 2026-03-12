def impact_score(severity: float, breadth: float, duration: float):
    score = float(severity) * 0.45 + float(breadth) * 0.30 + float(duration) * 0.25
    return round(min(1.0, max(0.0, score)), 3)
