# radar/levels.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List


@dataclass(frozen=True)
class Level:
    key: str
    label: str
    horizon: str
    typical_hold: str


LEVELS: List[Level] = [
    Level("scalp",   "0) Scalp",      "minuty–hodiny",  "5–90 min"),
    Level("day",     "0.5) Day",      "1 den",          "open→close"),
    Level("swing",   "1) Swing",      "dny–týdny",      "2–20 dní"),
    Level("position","2) Position",   "týdny–měsíce",   "3–16 týdnů"),
    Level("core",    "3) Core",       "měsíce–roky",    "6–36 měsíců"),
    Level("invest",  "4) Long-term",  "roky",           "3–10 let"),
]


def _sf(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def get_level(key: str) -> Level:
    k = (key or "").strip().lower()
    for lvl in LEVELS:
        if lvl.key == k:
            return lvl
    return LEVELS[3]


def pick_level(
    *,
    pct_from_open: Optional[float] = None,
    pct_1d: Optional[float] = None,
    vol_ratio: Optional[float] = None,
    has_catalyst: bool = False,
    score: Optional[float] = None,
) -> Tuple[str, Dict[str, Any]]:
    p_open = abs(_sf(pct_from_open) or 0.0)
    p_1d = abs(_sf(pct_1d) or 0.0)
    vr = _sf(vol_ratio) or 1.0
    sc = _sf(score)

    # intraday
    if pct_from_open is not None:
        if p_open >= 7:
            k = "day" if has_catalyst else "scalp"
            return k, _pack(k, p_open, p_1d, vr, sc)
        if p_open >= 3:
            k = "day" if has_catalyst else "swing"
            return k, _pack(k, p_open, p_1d, vr, sc)

    # daily
    if p_1d >= 6:
        return "swing", _pack("swing", p_open, p_1d, vr, sc)
    if p_1d >= 2.5:
        return ("swing" if (vr >= 1.4 and has_catalyst) else "position"), _pack(("swing" if (vr >= 1.4 and has_catalyst) else "position"), p_open, p_1d, vr, sc)

    # score fallback
    if sc is not None and sc >= 7.5:
        return "position", _pack("position", p_open, p_1d, vr, sc)

    return "core", _pack("core", p_open, p_1d, vr, sc)


def _pack(k: str, p_open: float, p_1d: float, vr: float, sc: Optional[float]) -> Dict[str, Any]:
    lvl = get_level(k)
    return {
        "level_key": k,
        "level_label": lvl.label,
        "horizon": lvl.horizon,
        "typical_hold": lvl.typical_hold,
        "pct_from_open_abs": p_open,
        "pct_1d_abs": p_1d,
        "vol_ratio": vr,
        "score": sc,
    }