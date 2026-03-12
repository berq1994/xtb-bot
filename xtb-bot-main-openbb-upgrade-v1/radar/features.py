# radar/features.py
from __future__ import annotations
from typing import Dict, Any, Optional


def movement_class(pct: Optional[float]) -> str:
    """
    Jednoduchá klasifikace pohybu (1D nebo od OPEN).
    """
    if pct is None:
        return "NO-DATA"
    a = abs(float(pct))
    if a >= 10:
        return "EXTREME"
    if a >= 6:
        return "STRONG"
    if a >= 3:
        return "MOVE"
    if a >= 1:
        return "DRIFT"
    return "FLAT"


def compute_features(raw: Dict[str, Any]) -> Dict[str, float]:
    """
    Převod raw metrik -> feature space (0..10), kompatibilní se scoringem.
    raw očekává klíče:
      pct_1d, momentum, rel_strength, vol_ratio, catalyst_score, regime_score
    """
    mom = float(raw.get("momentum") or 0.0)
    rs = float(raw.get("rel_strength") or 0.0)

    vol_ratio = raw.get("vol_ratio")
    try:
        vol_ratio = float(vol_ratio)
    except Exception:
        vol_ratio = 1.0

    cat = float(raw.get("catalyst_score") or 0.0)
    reg = float(raw.get("regime_score") or 5.0)

    # vol feature: 1.0 = normál, 2.0 ~ vyšší aktivita
    vol_feat = max(0.0, min(10.0, (vol_ratio - 1.0) * 6.0))

    # rs feature: map -5..+5 => 0..10 (clamp)
    rs_feat = max(0.0, min(10.0, (rs + 5.0) * 1.0))

    return {
        "momentum": max(0.0, min(10.0, mom)),
        "rel_strength": rs_feat,
        "volatility_volume": vol_feat,
        "catalyst": max(0.0, min(10.0, cat)),
        "market_regime": max(0.0, min(10.0, reg)),
    }