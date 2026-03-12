def build_live_briefing(rows: list):
    return {
        "title": "Live Intelligence Briefing",
        "top_items": rows[:5],
        "geo_count": len([x for x in rows if x.get("kind") == "geo"]),
        "earnings_count": len([x for x in rows if x.get("kind") == "earnings"]),
        "corporate_count": len([x for x in rows if x.get("kind") == "corporate"]),
        "macro_count": len([x for x in rows if x.get("kind") == "macro"]),
    }
