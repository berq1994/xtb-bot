# radar/universe.py
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from radar.config import RadarConfig


def resolved_universe(cfg: RadarConfig, universe: Optional[List[str]] = None) -> Tuple[List[str], Dict[str, str]]:
    """
    Returns:
      resolved: list[str]
      mapping: dict[str,str] raw -> resolved
    """
    base: List[str] = []
    if universe is None:
        base.extend([str(x).strip().upper() for x in (getattr(cfg, "watchlist", None) or [])])
        base.extend([str(x).strip().upper() for x in (getattr(cfg, "new_candidates", None) or [])])
    else:
        base.extend([str(x).strip().upper() for x in universe])

    seen = set()
    uniq: List[str] = []
    for t in base:
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)

    tm = getattr(cfg, "ticker_map", None) or {}
    norm_tm: Dict[str, str] = {}
    if isinstance(tm, dict):
        for k, v in tm.items():
            kk = str(k).strip().upper()
            vv = str(v).strip()
            if kk and vv:
                norm_tm[kk] = vv

    mapping: Dict[str, str] = {}
    resolved: List[str] = []
    for raw in uniq:
        res = norm_tm.get(raw, raw)
        mapping[raw] = res
        resolved.append(res)

    return resolved, mapping