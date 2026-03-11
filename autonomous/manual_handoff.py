def build_xtb_manual_handoff(impact_view: dict, governance: dict):
    lines = [
        "AUTONOMOUS XTB HANDOFF",
        f"Governance mode: {governance.get('mode')}",
        f"Manual XTB allowed: {governance.get('manual_xtb_allowed')}",
        "",
        "Co ručně zkontrolovat v xStation:",
    ]
    if not impact_view.get("high_priority"):
        lines.append("- Žádná kritická intelligence položka. Zaměř se na standardní watchlist.")
    else:
        for item in impact_view.get("high_priority", [])[:3]:
            hits = ", ".join(item.get("portfolio_hits", [])) or "-"
            lines.append(f"- {hits}: {item.get('headline')}")
    lines.append("")
    lines.append("Akce:")
    lines.append("- otevři watchlist")
    lines.append("- porovnej s ticketem a riskem")
    lines.append("- klik dělej jen po potvrzení setupu")
    return "\n".join(lines)
