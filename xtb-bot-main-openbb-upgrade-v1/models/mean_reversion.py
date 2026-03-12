from .base import ModelSignal

def run(symbol: str, snap: dict) -> ModelSignal:
    rsi = float(snap.get("rsi_14", 50.0))
    m1 = float(snap.get("move_1d_pct", 0.0))
    score = 0.0
    bias = "NEUTRAL"
    if rsi <= 30:
        score = (30 - rsi) * 0.7 + abs(m1) * 1.2
        bias = "LONG_REVERSION"
    elif rsi >= 70:
        score = (rsi - 70) * 0.7 + abs(m1) * 1.2
        bias = "SHORT_REVERSION"
    return ModelSignal("mean_reversion", symbol, round(score, 2), bias, f"RSI={rsi:.1f} 1D={m1:.2f}%", snap)
