def run_dashboard_agent(governance_mode: str, top_items: list):
    return {
        "governance_mode": governance_mode,
        "top_intelligence": top_items[:5],
    }
