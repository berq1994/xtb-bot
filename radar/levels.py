from __future__ import annotations

def pick_level(score: float, move_class: str) -> str:
    if score >= 70:
        return "A"
    if score >= 60:
        return "B"
    if score >= 45:
        return "C"
    return "D"