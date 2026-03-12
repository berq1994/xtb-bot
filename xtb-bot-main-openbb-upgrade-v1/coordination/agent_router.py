def route_research(kind: str):
    mapping = {
        "geo": "geo_research_agent",
        "corporate": "corporate_research_agent",
        "earnings": "earnings_research_agent",
        "macro": "macro_research_agent",
    }
    return mapping.get(kind, "research_coordinator")
