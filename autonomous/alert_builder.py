def build_autonomous_alerts(impact_view: dict):
    lines = []
    for item in impact_view.get("high_priority", [])[:5]:
        hits = ", ".join(item.get("portfolio_hits", [])) or "-"
        lines.append(f"ALERT | {item.get('headline')} | hits {hits} | impact {item.get('impact')}")
    return lines
