def to_briefing_section(title: str, items: list):
    return {
        "title": title,
        "count": len(items),
        "items": items[:5],
    }
