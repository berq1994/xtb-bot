from broker.live_http import simulate_request

def cancel_live_order(broker_order_id: str):
    return simulate_request("POST", f"/orders/{broker_order_id}/cancel")
