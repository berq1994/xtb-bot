from __future__ import annotations

from typing import Any, Dict, Tuple


def compute_score(cfg, feats: Dict[str, Any], pct_1d, vol_ratio: float, has_news: bool, regime_label: str, regime_score: float) -> Tuple[float, Dict[str, float]]:
    # jednoduché škálování (stabilní)
    score = 50.0
    parts: Dict[str, float] = {}

    # regime
    if regime_label == "RISK-ON":
        parts["regime"] = 6.0
    elif regime_label == "RISK-OFF":
        parts["regime"] = -6.0
    else:
        parts["regime"] = 0.0

    # 1D move
    if pct_1d is not None:
        parts["pct_1d"] = max(-8.0, min(8.0, float(pct_1d)))
    else:
        parts["pct_1d"] = 0.0

    # volume
    parts["vol"] = max(-2.0, min(6.0, (float(vol_ratio) - 1.0) * 3.0))

    # news
    parts["news"] = 2.0 if has_news else 0.0

    # feature
    if feats.get("ok"):
        parts["ret_20"] = max(-4.0, min(4.0, float(feats.get("ret_20") or 0.0) / 5.0))
    else:
        parts["ret_20"] = 0.0

    score = score + sum(parts.values())
    score = max(0.0, min(100.0, float(score)))
    return float(score), parts