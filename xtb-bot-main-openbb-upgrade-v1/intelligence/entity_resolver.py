def resolve_entities(text: str):
    text = (text or "").upper()
    found = []
    for token in ["NVDA", "MSFT", "AAPL", "TSM", "CVX", "LEU", "AMD", "BTC", "OIL", "IRAN", "TAIWAN", "FED"]:
        if token in text:
            found.append(token)
    return found
