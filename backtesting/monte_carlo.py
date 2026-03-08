import random

def monte_carlo_from_trades(trades: list, simulations: int = 200):
    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    if not pnls:
        return {"simulations": simulations, "median_final": 0.0, "p05": 0.0, "p95": 0.0}
    finals = []
    for _ in range(simulations):
        seq = random.choices(pnls, k=len(pnls))
        finals.append(sum(seq))
    finals.sort()
    return {
        "simulations": simulations,
        "median_final": finals[len(finals)//2],
        "p05": finals[max(0, int(len(finals)*0.05)-1)],
        "p95": finals[min(len(finals)-1, int(len(finals)*0.95))],
    }
