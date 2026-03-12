BULL = {"beat", "growth", "upgrade", "bullish", "strong", "surge", "wins", "raises"}
BEAR = {"miss", "downgrade", "bearish", "weak", "cuts", "lawsuit", "risk", "drop"}

def analyze_text(text: str) -> dict:
    low = (text or "").lower()
    pos = sum(1 for x in BULL if x in low)
    neg = sum(1 for x in BEAR if x in low)
    score = pos - neg
    label = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"
    return {"score": score, "label": label}
