def build_impact_view(mapped_events: list):
    relevant = [x for x in mapped_events if x.get("portfolio_relevant")]
    high_priority = [
        x for x in relevant
        if float(x.get("impact", 0)) >= 0.72 or float(x.get("relevance", 0)) >= 0.72
    ]
    return {
        "portfolio_relevant_count": len(relevant),
        "high_priority_count": len(high_priority),
        "high_priority": sorted(
            high_priority,
            key=lambda x: (float(x.get("impact", 0)), float(x.get("relevance", 0))),
            reverse=True,
        ),
    }
