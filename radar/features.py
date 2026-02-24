# radar/features.py
from __future__ import annotations
from typing import Dict


def movement_class(pct_1d: float | None) -> str:
    if pct_1d is None:
        return "NEZNÁMÝ"

    if pct_1d > 5:
        return "EXPLOZE"
    if pct_1d > 2:
        return "SILNÝ RŮST"
    if pct_1d > -2:
        return "NEUTRÁLNÍ"
    if pct_1d > -5:
        return "VÝPRODEJ"
    return "PANIKA"


def compute_features(price_data: Dict) -> Dict:
    """
    Dummy stabilní verze – nikdy nespadne
    """

    pct_1d = price_data.get("pct_1d")

    return {
        "momentum": price_data.get("momentum", 0),
        "rel_strength": price_data.get("rel_strength", 0),
        "volatility_volume": price_data.get("vol_ratio", 0),
        "catalyst": price_data.get("catalyst_score", 0),
        "market_regime": price_data.get("regime_score", 0),
        "movement": movement_class(pct_1d),
    }