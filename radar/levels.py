# radar/levels.py
from __future__ import annotations


def pick_level(score: float, movement_class: str) -> str:
    """
    Jednoduché labely:
    - A/B/C podle score
    - doplněk podle typu pohybu
    """
    try:
        s = float(score)
    except Exception:
        s = 0.0

    if s >= 75:
        base = "A"
    elif s >= 55:
        base = "B"
    else:
        base = "C"

    mc = (movement_class or "NORMAL").upper()
    if mc == "BIG_MOVE":
        return f"{base}-BIG"
    if mc == "MOVE":
        return f"{base}-MOVE"
    if mc == "VOLUME_SPIKE":
        return f"{base}-VOL"
    return base