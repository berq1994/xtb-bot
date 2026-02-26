# radar/scoring.py
from __future__ import annotations
from typing import Dict


def compute_score(features: Dict[str, float], weights: Dict[str, float]) -> float:
    """
    Vážené skóre 0..10 (weights se očekávají normalizované, ale když nejsou, přeškálujeme).
    """
    if not weights:
        return 0.0

    # normalizace vah “za běhu”
    s = sum(float(v) for v in weights.values() if isinstance(v, (int, float)))
    if s <= 0:
        return 0.0

    score = 0.0
    for k, w in weights.items():
        if k in features:
            score += (float(w) / s) * float(features[k])
    return float(score)