def route_command(command: str):
    mapping = {
        "/briefing": "send_latest_briefing",
        "/alerts": "send_latest_alerts",
        "/watchlist": "send_watchlist",
        "/ticket": "send_manual_ticket",
        "/journal": "send_journal",
    }
    return {"command": command, "action": mapping.get(command, "unknown")}
