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
    vol_ratio = raw.get("vol_ratio", 1.0) or 1.0
    catalyst_score = raw.get("catalyst_score", 0.0) or 0.0
    regime_score = raw.get("regime_score", 5.0) or 5.0

    # momentum už typicky 0..10
    mom = float(momentum)

    # RS: map -5..+5 => 0..10 (ořez)
    rs = float(rel_strength)
    rs_norm = max(0.0, min(10.0, (rs + 5.0)))

    # volume ratio: 1.0 normál; 2.0 ~ výrazně; map => 0..10
    vr = float(vol_ratio)
    vol_norm = max(0.0, min(10.0, (vr - 1.0) * 6.0))

    # catalyst: 0..10
    cat = max(0.0, min(10.0, float(catalyst_score)))

    # regime: 0..10
    reg = max(0.0, min(10.0, float(regime_score)))

    return {
        "movement": 0.0 if pct_1d is None else float(abs(pct_1d)),
        "momentum": mom,
        "rel_strength": rs_norm,
        "volatility_volume": vol_norm,
        "catalyst": cat,
        "market_regime": reg,
    }