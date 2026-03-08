from broker.live_http import simulate_request

def submit_live_order(mapped_order: dict):
    return simulate_request("POST", "/orders", payload=mapped_order)
