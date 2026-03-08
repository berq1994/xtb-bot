def dd_status(current_dd_pct: float, soft_limit: float, hard_limit: float):
    if current_dd_pct <= -hard_limit:
        return {"status":"HARD_STOP", "multiplier":0.0}
    if current_dd_pct <= -soft_limit:
        return {"status":"SOFT_LIMIT", "multiplier":0.5}
    return {"status":"OK", "multiplier":1.0}
