from __future__ import annotations

from typing import Any, Dict, List

def md_bullets(lines: List[str]) -> str:
    return "\n".join([f"- {x}" for x in lines if x])

def safe_pct(x: Any) -> str:
    try:
        return f"{float(x):+.2f}%"
    except Exception:
        return "n/a"