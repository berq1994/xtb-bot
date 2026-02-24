# radar/scoring.py
from __future__ import annotations
from typing import Dict, Any, Optional


def safe(x: Optional[float], default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def compute_score(features: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """
    Hlavní scoring model (lehce profesionální, stabilní, deterministic).
    """

    weights = cfg.get("weights", {})

    w_momentum = float(weights.get("momentum", 0.25))
    w_rs = float(weights.get("rel_strength", 0.20))
    w_vol = float(weights.get("volatility_volume", 0.15))
    w_cat = float(weights.get("catalyst", 0.20))
    w_regime = float(weights.get("market_regime", 0.20))

    pct_1d = safe(features.get("pct_1d"))
    rs_5d = safe(features.get("rs_5d"))
    vol_ratio = safe(features.get("vol_ratio"), 1.0)

    movement = features.get("movement", "FLAT")

    # --------------------------------------------------------
    # Momentum komponenta
    # --------------------------------------------------------
    momentum_score = abs(pct_1d)

    # --------------------------------------------------------
    # Relative strength komponenta
    # --------------------------------------------------------
    rs_score = abs(rs_5d)

    # --------------------------------------------------------
    # Volume / volatility komponenta
    # --------------------------------------------------------
    vol_score = max(vol_ratio - 1.0, 0.0)

    # --------------------------------------------------------
    # Catalyst komponenta (earnings/news)
    # --------------------------------------------------------
    catalyst_score = 0.0
    if features.get("news"):
        catalyst_score += 1.0

    dte = features.get("days_to_earnings")
    if dte is not None:
        if dte <= 3:
            catalyst_score += 1.5
        elif dte <= 10:
            catalyst_score += 0.5

    # --------------------------------------------------------
    # Market regime komponenta (zjednodušená stabilní logika)
    # --------------------------------------------------------
    regime = cfg.get("market_regime", "NEUTRAL")

    regime_mult = 1.0
    if regime == "RISK_OFF":
        if pct_1d < 0:
            regime_mult = 1.2
        else:
            regime_mult = 0.8

    if regime == "RISK_ON":
        if pct_1d > 0:
            regime_mult = 1.2
        else:
            regime_mult = 0.8

    # --------------------------------------------------------
    # Celkové score
    # --------------------------------------------------------
    score = (
        momentum_score * w_momentum
        + rs_score * w_rs
        + vol_score * w_vol
        + catalyst_score * w_cat
    )

    return round(score * regime_mult, 4)