import math
import pandas as pd

def sharpe_ratio(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) < 2 or r.std() == 0:
        return 0.0
    return float((r.mean() / r.std()) * math.sqrt(252))

def sortino_ratio(returns: pd.Series) -> float:
    r = returns.dropna()
    downside = r[r < 0]
    if len(r) < 2 or len(downside) < 1 or downside.std() == 0:
        return 0.0
    return float((r.mean() / downside.std()) * math.sqrt(252))

def max_drawdown(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min())

def win_rate(trades: list) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    return wins / len(trades)

def profit_factor(trades: list) -> float:
    wins = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
    losses = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))
    if losses == 0:
        return wins if wins > 0 else 0.0
    return wins / losses
