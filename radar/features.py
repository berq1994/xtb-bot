# radar/features.py
from __future__ import annotations

from typing import Dict, Any, Optional


def movement_class(pct: Optional[float]) -> str:
    if pct is None:
        return "—"
    a = abs(pct)
    if a >= 7:
        return "🟧 UDÁLOSTNÍ DEN"
    if a >= 3:
        return "🟨 VOLATILNÍ"
    if a >= 1:
        return "🟩 NORMÁL"
    return "⬜ KLID"


def compute_features(raw: Dict[str, Any]) -> Dict[str, float]:
    pct_1d = raw.get("pct_1d")
    momentum = float(raw.get("momentum", 0.0) or 0.0)
    rel_strength = float(raw.get("rel_strength", 0.0) or 0.0)
    vol_ratio = float(raw.get("vol_ratio", 1.0) or 1.0)
    catalyst = float(raw.get("catalyst_score", 0.0) or 0.0)
    regime = float(raw.get("regime_score", 5.0) or 5.0)

    # jednoduché normalizace do 0..10
    vol_score = min(10.0, max(0.0, (vol_ratio - 1.0) * 5.0))  # 1.0 => 0, 3.0 => 10

    feat = {
        "momentum": float(momentum),
        "rel_strength": float(rel_strength),
        "volatility_volume": float(vol_score),
        "catalyst": float(catalyst),
        "market_regime": float(regime),
    }
    feat["movement"] = 0.0  # placeholder (nepočítáme do score)
    return feat