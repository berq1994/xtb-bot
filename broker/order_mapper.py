def map_internal_order(order: dict):
    return {
        "symbol": order.get("symbol"),
        "side": order.get("side"),
        "quantity": float(order.get("qty", 0) or 0),
        "type": order.get("type", "MARKET"),
        "time_in_force": order.get("tif", "DAY"),
    }
