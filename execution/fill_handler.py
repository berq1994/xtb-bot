def handle_fill(order: dict, fill_qty: float, fill_price: float):
    remaining = max(0.0, float(order.get("qty", 0)) - float(fill_qty))
    status = "FILLED" if remaining == 0 else "PARTIALLY_FILLED"
    return {
        "symbol": order.get("symbol"),
        "filled_qty": fill_qty,
        "fill_price": fill_price,
        "remaining_qty": remaining,
        "status": status,
    }
