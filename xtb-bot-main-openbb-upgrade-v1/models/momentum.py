from .base import ModelSignal

def run(symbol: str, snap: dict) -> ModelSignal:
    m1 = float(snap.get("move_1d_pct", 0.0))
    m5 = float(snap.get("move_5d_pct", 0.0))
    vol = float(snap.get("volume_spike", 1.0))
    score = max(0.0, m1 * 7 + m5 * 2 + (vol - 1.0) * 8)
    bias = "LONG" if score >= 8 else "NEUTRAL"
    return ModelSignal("momentum", symbol, round(score, 2), bias, f"1D={m1:.2f}% 5D={m5:.2f}% vol={vol:.2f}x", snap)
