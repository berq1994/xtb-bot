def rank_items(items: list):
    return sorted(items, key=lambda x: (float(x.get("impact", 0)), float(x.get("relevance", 0))), reverse=True)
