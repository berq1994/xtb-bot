from execution.router import route_orders

def run_execution(risk_payload):
    return route_orders(risk_payload.get("portfolio", []))


