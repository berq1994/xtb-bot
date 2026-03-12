def build_agent_ticket(symbol: str, score: float):
    return {
        "symbol": symbol,
        "score": score,
        "ticket_ready": True,
        "note": "PĹ™edat do manual trade ticket builderu.",
    }


