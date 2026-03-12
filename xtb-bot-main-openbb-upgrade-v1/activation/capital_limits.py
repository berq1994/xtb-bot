def check_capital_limits(order_notional_usd: float, open_positions: int, limits: dict):
    max_order = float(limits.get("semi_live_max_order_usd", 0))
    max_positions = int(limits.get("semi_live_max_positions", 0))

    reasons = []
    if order_notional_usd > max_order:
        reasons.append("ORDER_NOTIONAL_LIMIT")
    if open_positions >= max_positions:
        reasons.append("MAX_POSITIONS_REACHED")

    return {
        "approved": len(reasons) == 0,
        "reasons": reasons or ["OK"],
    }
