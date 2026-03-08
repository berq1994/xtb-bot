def volatility_score(hist_vol: float | None, atr_pct: float | None) -> dict:
    hv = float(hist_vol or 0.0)
    ap = float(atr_pct or 0.0)
    score = min(100.0, hv * 100 + ap * 10)
    state = "LOW" if score < 25 else "MID" if score < 55 else "HIGH"
    return {"score": round(score, 2), "state": state}
