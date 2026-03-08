def validate_order(order: dict, max_qty: float = 1000.0):
    reasons = []
    if not order.get("symbol"):
        reasons.append("MISSING_SYMBOL")
    if order.get("side") not in ["BUY", "SELL"]:
        reasons.append("INVALID_SIDE")
    qty = float(order.get("qty", 0) or 0)
    if qty <= 0:
        reasons.append("INVALID_QTY")
    if qty > max_qty:
        reasons.append("QTY_LIMIT_EXCEEDED")

    return {
        "approved": len(reasons) == 0,
        "reasons": reasons or ["OK"],
    }
