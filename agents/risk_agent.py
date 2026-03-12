from portfolio.var_engine import compute_portfolio_var
from portfolio.drawdown_engine import drawdown_guard
from portfolio.construction import build_portfolio

def run_risk(signal_payload):
    portfolio = build_portfolio(signal_payload)
    var = compute_portfolio_var(portfolio)
    dd = drawdown_guard(current_dd_pct=-0.05, soft_limit=10.0, hard_limit=15.0)
    return {"portfolio": portfolio, "var": var, "drawdown": dd}


