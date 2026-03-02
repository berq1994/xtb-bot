from __future__ import annotations

from typing import List

from radar.config import RadarConfig


def resolved_universe(cfg: RadarConfig) -> List[str]:
    # vždy list stringů
    uni = cfg.universe or []
    out = []
    for x in uni:
        if not x:
            continue
        out.append(str(x).strip().upper())
    # dedupe
    seen = set()
    final = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        final.append(t)
    return final