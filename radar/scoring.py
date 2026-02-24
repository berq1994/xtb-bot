# radar/scoring.py
from __future__ import annotations
from typing import Dict


def compute_score(features: Dict, weights: Dict) -> float:
    """
    Jednoduchý vážený scoring model
    features = výstup z compute_features()
    weights  = config.yml → weights
    """

    score = 0.0

    def w(name: str) -> float:
        try:
            return float(weights.get(name, 0))
        except Exception:
            return 0.0

    def f(name: str) -> float:
        try:
            val = features.get(name, 0)
            return float(val) if val is not None else 0.0
        except Exception:
            return 0.0

    score += f("momentum") * w("momentum")
    score += f("rel_strength") * w("rel_strength")
    score += f("volatility_volume") * w("volatility_volume")
    score += f("catalyst") * w("catalyst")
    score += f("market_regime") * w("market_regime")

    return round(score, 4)