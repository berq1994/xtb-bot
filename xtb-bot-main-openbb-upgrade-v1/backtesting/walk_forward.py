from backtesting.run import run_portfolio_backtest
from ai.experiment_tracker import log_experiment

def run_walk_forward():
    # Minimal practical version for current repo
    summary = run_portfolio_backtest()
    payload = {"mode":"walk_forward_stub", "summary": summary}
    log_experiment("walk_forward", payload)
    return payload
