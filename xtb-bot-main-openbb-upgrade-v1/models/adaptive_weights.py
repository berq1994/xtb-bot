from __future__ import annotations
from pathlib import Path
import json

STATE = Path(".state")
STATE.mkdir(exist_ok=True)
FILE = STATE / "adaptive_weights.json"

DEFAULT = {
    "momentum": 0.25,
    "breakout": 0.20,
    "mean_reversion": 0.10,
    "sentiment": 0.15,
    "regime": 0.10,
    "volatility": 0.10,
    "lstm": 0.05,
    "transformer": 0.05,
}

def load_weights():
    if FILE.exists():
        try:
            return json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT.copy()

def save_weights(weights: dict):
    total = sum(weights.values()) or 1.0
    norm = {k: round(v / total, 6) for k, v in weights.items()}
    FILE.write_text(json.dumps(norm, ensure_ascii=False, indent=2), encoding="utf-8")
    return norm

def update_weights_from_scores(scores: dict, learning_rate: float = 0.30):
    weights = load_weights()

    for model, score in scores.items():
        if model not in weights:
            continue
        base = weights[model]
        adjustment = max(-1.0, min(1.0, float(score))) * learning_rate
        weights[model] = max(0.01, base * (1.0 + adjustment))

    return save_weights(weights)
