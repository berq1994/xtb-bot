# radar/scoring.py
from __future__ import annotations

from typing import Any, Dict, Tuple


def compute_score(
    cfg,
    feats: Dict[str, Any],
    pct_1d,
    vol_ratio: float,
    has_news: bool,
    regime_label: str,
    regime_score: float,
) -> Tuple[float, Dict[str, float]]:
    """
    Stabilní jednoduché skóre (0..100):
    - momentum (pct_1d)
    - volume
    - volatility (atr)
    - catalyst (news)
    - market_regime

    Váhy bere z cfg.weights (normalizované nebo ne – ošetříme).
    """
    w = getattr(cfg, "weights", None) or {}
    # fallback
    def wv(k, d):
        try:
            return float(w.get(k, d))
        except Exception:
            return float(d)

    # normalizace vah
    keys = ["momentum", "volume", "volatility", "catalyst", "market_regime"]
    raw = {k: wv(k, 0.2) for k in keys}
    s = sum(raw.values()) or 1.0
    ww = {k: raw[k] / s for k in keys}

    parts: Dict[str, float] = {k: 0.0 for k in keys}

    # momentum: -10..+10% mapujeme zhruba na 0..1
    if pct_1d is None:
        mom = 0.5
    else:
        p = float(pct_1d)
        mom = max(0.0, min(1.0, (p + 10.0) / 20.0))
    parts["momentum"] = mom

    # volume ratio: 0.5..2.5 mapujeme na 0..1
    vr = float(vol_ratio or 1.0)
    vol = max(0.0, min(1.0, (vr - 0.5) / 2.0))
    parts["volume"] = vol

    # volatility: nižší atr = “klidnější” (pro trend), ale necháme neutrálně
    atr = float(feats.get("atr14") or 0.03)
    # 0.01..0.08 -> 1..0
    volat = max(0.0, min(1.0, (0.08 - atr) / 0.07))
    parts["volatility"] = volat

    # catalyst
    parts["catalyst"] = 1.0 if has_news else 0.3

    # market regime
    if regime_label == "RISK-ON":
        mr = 1.0
    elif regime_label == "RISK-OFF":
        mr = 0.2
    else:
        mr = 0.6
    parts["market_regime"] = mr

    score01 = (
        ww["momentum"] * parts["momentum"]
        + ww["volume"] * parts["volume"]
        + ww["volatility"] * parts["volatility"]
        + ww["catalyst"] * parts["catalyst"]
        + ww["market_regime"] * parts["market_regime"]
    )

    score = float(score01 * 100.0)
    return score, {k: float(parts[k]) for k in parts}