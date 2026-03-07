# radar/levels.py
from __future__ import annotations
from typing import Dict, Tuple, Optional


LEVELS: Dict[str, Dict[str, str]] = {
    "SCALP": {"level_label": "LEVEL 0 – SCALP (minuty–hodiny)"},
    "DAY": {"level_label": "LEVEL 1 – DAY (intradenní)"},
    "SWING": {"level_label": "LEVEL 2 – SWING (dny–týdny)"},
    "POSITION": {"level_label": "LEVEL 3 – POSITION (týdny–měsíce)"},
    "INVEST": {"level_label": "LEVEL 4 – INVEST (měsíce–roky)"},
}


def pick_level(
    pct_from_open: Optional[float],
    pct_1d: Optional[float],
    vol_ratio: float,
    has_catalyst: bool,
    score: float,
) -> Tuple[str, Dict[str, str]]:
    """
    Heuristika:
      - když je intraday velká (pct_from_open), je to day/scalp
      - když je 1D velká + catalyst/volume, typicky swing
      - vyšší score bez chaosu = position/invest
    """
    a_open = abs(pct_from_open) if pct_from_open is not None else 0.0
    a_1d = abs(pct_1d) if pct_1d is not None else 0.0

    if a_open >= 6 or (a_open >= 3 and vol_ratio >= 2.0):
        key = "DAY" if a_open < 8 else "SCALP"
        return key, LEVELS[key]

    if a_1d >= 6 or (a_1d >= 3 and (has_catalyst or vol_ratio >= 1.8)):
        return "SWING", LEVELS["SWING"]

    if score >= 7.5:
        return "POSITION", LEVELS["POSITION"]

    if score >= 6.0:
        return "INVEST", LEVELS["INVEST"]

    return "INVEST", LEVELS["INVEST"]