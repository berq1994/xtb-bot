def route_orders(portfolio):
    return {"mode": "paper", "orders": portfolio, "slippage_bps": 5, "latency_ms": 120}
