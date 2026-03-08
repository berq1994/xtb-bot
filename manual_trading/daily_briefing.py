def build_daily_briefing(final_mode: str, governance_mode: str, ranked_watchlist: list, market_note: str):
    return {
        "final_mode": final_mode,
        "governance_mode": governance_mode,
        "market_note": market_note,
        "top_watchlist": ranked_watchlist[:5],
        "actions": [
            "Sledovat první 2 tickery z watchlistu při open.",
            "Neotvírat obchod bez potvrzeného SL.",
            "Pokud je performance gate slabá, být selektivní a brát jen A setupy.",
        ],
    }
