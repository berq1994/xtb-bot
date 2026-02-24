from typing import Optional, Dict, Any
from radar.features import movement_class


def clamp(x: float, lo=0.0, hi=10.0) -> float:
    return max(lo, min(hi, x))


def momentum_score_1d(pct1d: Optional[float]) -> float:
    if pct1d is None:
        return 0.0
    # škála: 0..8% => 0..10
    return clamp((abs(pct1d) / 8.0) * 10.0, 0.0, 10.0)


def rs_score(rs: Optional[float]) -> float:
    if rs is None:
        return 0.0
    # -5..+5 => 0..10
    return clamp((rs + 5.0) * 1.0, 0.0, 10.0)


def vol_score(vol_ratio: float) -> float:
    # 1.0 = normál, 2.0 = hodně
    return clamp((vol_ratio - 1.0) * 6.0, 0.0, 10.0)


def catalyst_score(news_count: int) -> float:
    # 0..(>=4) => 0..10
    if news_count <= 0:
        return 0.0
    return clamp(2.0 + news_count * 2.0, 0.0, 10.0)


def regime_score(regime_label: str) -> float:
    if regime_label == "RISK-ON":
        return 10.0
    if regime_label == "RISK-OFF":
        return 0.0
    return 5.0


def total_score(weights: Dict[str, float], mom: float, rs: float, vol: float, cat: float, reg: float) -> float:
    return (
        weights["momentum"] * mom +
        weights["rel_strength"] * rs +
        weights["volatility_volume"] * vol +
        weights["catalyst"] * cat +
        weights["market_regime"] * reg
    )


def advice_soft(score: float, regime: str) -> str:
    if regime == "RISK-OFF":
        if score >= 7.5:
            return "Silné, ale trh je RISK-OFF: radši konzervativně / menší pozice / čekat na timing."
        if score <= 3.0:
            return "Slabé + RISK-OFF: nedokupovat, zvážit redukci dle plánu."
        return "RISK-OFF: spíš HOLD a čekat na katalyzátor."
    else:
        if score >= 7.5:
            return "Kandidát na přikoupení / vstup (dle rizika)."
        if score <= 3.0:
            return "Kandidát na redukci / prodej (pokud sedí do plánu)."
        return "Neutrální: HOLD / čekat."