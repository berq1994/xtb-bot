def submit_order(order: dict, live_enabled: bool = False):
    if not live_enabled:
        return {
            "submitted": True,
            "mode": "paper_stub",
            "broker_order_id": f"paper-{order.get('symbol', 'UNK')}",
        }
    return {
        "submitted": False,
        "mode": "live_disabled_stub",
        "broker_order_id": None,
    }
