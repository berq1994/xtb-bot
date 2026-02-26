# radar/scoring.py
from __future__ import annotations
from typing import Dict


def compute_score(features: Dict[str, float], weights: Dict[str, float]) -> float:
    """
    features: dict s klíči:
      momentum, rel_strength, volatility_volume, catalyst, market_regime
    weights: stejné klíče, ideálně normalizované (součet 1)
    """
    w = dict(weights or {})
    # fallback váhy
    for k in ("momentum", "rel_strength", "volatility_volume", "catalyst", "market_regime"):
        w.setdefault(k, 0.2)

    s = (
        w["momentum"] * features.get("momentum", 0.0) +
        w["rel_strength"] * features.get("rel_strength", 0.0) +
        w["volatility_volume"] * features.get("volatility_volume", 0.0) +
        w["catalyst"] * features.get("catalyst", 0.0) +
        w["market_regime"] * features.get("market_regime", 0.0)
    )
    # score 0..10
    return max(0.0, min(10.0, float(s)))