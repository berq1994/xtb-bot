from supervisor.state_manager import load_state, save_state

def evaluate_policies(summary: dict) -> dict:
    state = load_state()
    decision = {
        "safe_mode": state.get("safe_mode", False),
        "allow_recalibration": True,
        "allow_trading_tasks": True,
        "reason": "OK",
    }

    drawdown = float(summary.get("max_drawdown", 0.0) or 0.0)
    if drawdown <= -0.18:
        decision["safe_mode"] = True
        decision["allow_recalibration"] = False
        decision["allow_trading_tasks"] = False
        decision["reason"] = "HARD_DRAWDOWN_LIMIT"

    missing_ratio = float(summary.get("missing_data_ratio_pct", 0.0) or 0.0)
    if missing_ratio >= 25.0:
        decision["allow_recalibration"] = False
        decision["reason"] = "DATA_QUALITY_LOW"

    state["safe_mode"] = decision["safe_mode"]
    save_state(state)
    return decision
