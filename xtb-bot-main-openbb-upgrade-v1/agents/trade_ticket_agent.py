def build_agent_ticket(symbol: str, score: float):
    return {
        "symbol": symbol,
        "score": score,
        "ticket_ready": True,
        "note": "Předat do manual trade ticket builderu.",
    }
