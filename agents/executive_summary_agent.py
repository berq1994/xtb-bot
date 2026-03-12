def run_executive_summary_agent(governance_mode: str, top_items: list):
    return {
        "summary_cz": f"Režim systému: {governance_mode}. Nejvyšší prioritu mají {len(top_items[:3])} intelligence položky.",
    }
