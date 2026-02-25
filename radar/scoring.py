# radar/scoring.py
from __future__ import annotations

from typing import Dict


def compute_score(features: Dict[str, float], weights: Dict[str, float]) -> float:
    s = 0.0
    for k, w in (weights or {}).items():
        s += float(features.get(k, 0.0)) * float(w)
    return float(s)