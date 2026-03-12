from .base import ModelSignal

def run(symbol: str, snap: dict) -> ModelSignal:
    br = bool(snap.get("breakout_20d", False))
    dist = float(snap.get("close_vs_20d_high_pct", 0.0))
    vol = float(snap.get("volume_spike", 1.0))
    score = (10 if br else 0) + max(0.0, dist * 100) + max(0.0, (vol - 1.0) * 6)
    bias = "LONG" if score >= 8 else "WATCH"
    return ModelSignal("breakout", symbol, round(score, 2), bias, f"breakout={br} dist={dist:.2%} vol={vol:.2f}x", snap)
