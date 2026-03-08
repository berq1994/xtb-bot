BULLISH = {"beat","growth","upgrade","bullish","strong","surge","ai demand","inflow","wins","raises"}
BEARISH = {"miss","downgrade","bearish","weak","cuts","lawsuit","risk","drop","outflow","delay"}

def score_text(text: str) -> dict:
    low = (text or "").lower()
    pos = sum(1 for token in BULLISH if token in low)
    neg = sum(1 for token in BEARISH if token in low)
    score = pos - neg
    label = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"
    confidence = min(1.0, (abs(score) / 4.0))
    return {"label": label, "score": score, "confidence": round(confidence, 2)}
