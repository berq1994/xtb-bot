from __future__ import annotations

import os
from typing import Any

DEFAULT_FX_TO_CZK = {
    "CZK": 1.0,
    "USD": 23.0,
    "EUR": 25.0,
    "GBP": 29.0,
}


def fx_to_czk(ccy: str | None) -> float:
    code = str(ccy or "CZK").strip().upper() or "CZK"
    env_key = f"FX_{code}_CZK"
    try:
        raw = float(str(os.getenv(env_key) or "").strip())
        if raw > 0:
            return raw
    except Exception:
        pass
    return DEFAULT_FX_TO_CZK.get(code, 1.0)


def native_value_to_czk(value: Any, ccy: str | None) -> float:
    try:
        amount = float(value or 0.0)
    except Exception:
        amount = 0.0
    return round(amount * fx_to_czk(ccy), 2)
