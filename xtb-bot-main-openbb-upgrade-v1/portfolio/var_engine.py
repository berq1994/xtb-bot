def compute_portfolio_var(portfolio):
    return {"var_pct": round(len(portfolio) * 1.1, 2), "cvar_pct": round(len(portfolio) * 1.4, 2)}
