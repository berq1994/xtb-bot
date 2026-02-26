# radar/features.py
from __future__ import annotations

from typing import Dict, Any, Optional


def movement_class(pct: Optional[float]) -> str:
    if pct is None:
        return "NO_DATA"
    a = abs(pct)
    if a >= 10:
        return "EXTRÉM"
    if a >= 6:
        return "VELKÝ"
    if a >= 3:
        return "STŘEDNÍ"
    if a >= 1:
        return "MALÝ"
    return "MINI"


def compute_features(raw: Dict[str, Any]) -> Dict[str, float]:
    """
    Převede raw vstupy do normalizovaných (0..10) feature values.
    """
    pct_1d = raw.get("pct_1d")
    momentum = raw.get("momentum", 0.0) or 0.0
    rel_strength = raw.get("rel_strength", 0.0) or 0.0
    vol_ratio = raw