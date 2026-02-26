# radar/levels.py
from __future__ import annotations
from typing import Dict, Tuple, Optional


LEVELS: Dict[str, Dict[str, str]] = {
    "L0": {"level_label": "L0 – Info"},
    "L1": {"level_label": "L1 – Watch"},
    "L2": {"level_label": "L2 – Setup"},
    "L3": {"level_label": "L3 – Swing kandidát"},
    "L4": {"level_label": "L4 – Momentum / Breakout"},
    "L5": {"level_label": "L5 – High conviction (pozor na risk)"},
}


def pick_level(
    pct_from_open: Optional[float],
    pct_1d: Optional[float],
    vol_ratio: float,
    has_catalyst: bool,
    score: float,
) -> Tuple[str, Dict[str, str]]:
    """
    Jednoduché, ale stabilní:
    - score a volatilita + catalyst => level
    """
    if score >= 8.5 and (has_catalyst or vol_ratio >= 1.5):
        return "L5", LEVELS["L5"]
    if score >= 7.6 and (pct_1d is not None and abs(pct_1d) >= 2.0):
        return "L4", LEVELS["L4"]
    if score >= 6.8 and (vol_ratio >= 1.2 or has_catalyst):
        return "L3", LEVELS["L3"]
    if score >= 5.5:
        return "L2", LEVELS["L2"]
    if score >= 4.0:
        return "L1", LEVELS["L1"]
    return "L0", LEVELS["L0"]