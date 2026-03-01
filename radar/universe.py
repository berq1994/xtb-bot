# radar/universe.py
from __future__ import annotations

from typing import List
from radar.config import RadarConfig


def resolved_universe(cfg: RadarConfig) -> List[str]:
    """
    Základní univerzum:
    - watchlist z configu
    - + případně new_candidates, pokud existuje v configu
    """
    uni: List[str] = []
    wl = getattr(cfg, "watchlist", None) or []
    for t in wl:
        s = str(t).strip().upper()
        if s and s not in uni:
            uni.append(s)

    nc = getattr(cfg, "new_candidates", None) or []
    for t in nc:
        s = str(t).strip().upper()
        if s and s not in uni:
            uni.append(s)

    return uni