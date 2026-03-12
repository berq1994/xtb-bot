def compute_position_size(entry_price: float, stop_price: float, risk_capital_usd: float):
    entry_price = float(entry_price)
    stop_price = float(stop_price)
    risk_capital_usd = float(risk_capital_usd)

    per_share_risk = abs(entry_price - stop_price)
    if per_share_risk <= 0:
        return {
            "shares": 0,
            "per_share_risk": 0.0,
            "position_notional_usd": 0.0,
            "total_risk_usd": 0.0,
        }

    shares = int(risk_capital_usd // per_share_risk)
    notional = shares * entry_price
    total_risk = shares * per_share_risk

    return {
        "shares": shares,
        "per_share_risk": round(per_share_risk, 4),
        "position_notional_usd": round(notional, 2),
        "total_risk_usd": round(total_risk, 2),
    }
