# radar/features.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional


def movement_class(pct: Optional[float]) -> str:
    """
    Klasifikace pohybu (jednoduchá, ale užitečná).
    pct = procenta (např. +3.2 nebo -6.8)

    Vrací krátký label, který pak použijeme v reportech/alertech.
    """
    if pct is None:
        return "NO_DATA"

    a = abs(pct)
    if a >= 12:
        return "EXTREMNÍ POHYB"
    if a >= 7:
        return "VELKÝ POHYB"
    if a >= 3:
        return "STŘEDNÍ POHYB"
    if a >= 1:
        return "MALÝ POHYB"
    return "MIKRO POHYB"


def compute_features(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Převod surových dat -> feature set pro scoring.
    Čekáme klíče:
      - pct_1d (float|None)
      - momentum (0..10)
      - rel_strength (0..10 nebo 0..??)
      - vol_ratio (float)
      - catalyst_score (0..10)
      - regime_score (0..10)
    """
    pct_1d = raw.get("pct_1d", None)
    mv = movement_class(pct_1d)

    return {
        "pct_1d": pct_1d,
        "movement": mv,
        "momentum": float(raw.get("momentum", 0.0) or 0.0),
        "rel_strength": float(raw.get("rel_strength", 0.0) or 0.0),
        "vol_ratio": float(raw.get("vol_ratio", 1.0) or 1.0),
        "catalyst_score": float(raw.get("catalyst_score", 0.0) or 0.0),
        "regime_score": float(raw.get("regime_score", 5.0) or 5.0),
    }