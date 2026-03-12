def portfolio_var(positions_count: int, avg_risk_per_trade_pct: float = 1.0) -> float:
    # conservative proxy
    return round(positions_count * avg_risk_per_trade_pct, 2)
