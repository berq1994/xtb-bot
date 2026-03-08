from broker.live_http import simulate_request

def get_live_order_status(broker_order_id: str):
    return simulate_request("GET", f"/orders/{broker_order_id}")
