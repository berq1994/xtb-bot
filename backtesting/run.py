from pathlib import Path
import yaml
import pandas as pd

from .engine import run_backtest_for_symbol
from .metrics import sharpe_ratio, sortino_ratio, max_drawdown, win_rate, profit_factor
from .equity import save_equity_curve, save_performance_summary, save_trade_log

def load_tickers():
    config_main = Path("config.yml")
    config_alt = Path("config/radar_g_settings.yml")
    tickers = []

    if config_main.exists():
        try:
            data = yaml.safe_load(config_main.read_text(encoding="utf-8")) or {}
            if isinstance(data.get("tickers"), list):
                tickers.extend(data["tickers"])
            if isinstance(data.get("portfolio"), list):
                tickers.extend(data["portfolio"])
        except Exception:
            pass

    if config_alt.exists():
        try:
            data = yaml.safe_load(config_alt.read_text(encoding="utf-8")) or {}
            tickers.extend(data.get("default_tickers", []))
        except Exception:
            pass

    seen = set()
    ordered = []
    for t in tickers:
        if t and t not in seen:
            ordered.append(t)
            seen.add(t)
    return ordered

def run_portfolio_backtest():
    cfg = yaml.safe_load(Path("config/radar_g_settings.yml").read_text(encoding="utf-8"))
    capital = float(cfg["radar_g"]["start_capital"])
    risk = float(cfg["radar_g"]["risk_per_trade"])
    period = cfg["radar_g"]["lookback_period"]
    interval = cfg["radar_g"]["interval"]

    tickers = load_tickers()
    if not tickers:
        raise RuntimeError("Nenalezeny žádné tickery v config.yml ani radar_g_settings.yml")

    all_trades = []
    curves = []

    capital_per_symbol = capital / max(1, len(tickers))
    for symbol in tickers:
        res = run_backtest_for_symbol(symbol, capital_per_symbol, risk, period=period, interval=interval)
        trades = res["trades"]
        eq = res["equity_curve"].copy()
        if not eq.empty:
            eq = eq.rename(columns={"equity": symbol})
            curves.append(eq)
        all_trades.extend(trades)

    if curves:
        equity = pd.concat(curves, axis=1).ffill().fillna(capital_per_symbol)
        equity["equity"] = equity.sum(axis=1)
    else:
        equity = pd.DataFrame({"equity": [capital]}, index=[pd.Timestamp.today()])

    returns = equity["equity"].pct_change().dropna()
    summary = {
        "tickers": tickers,
        "final_equity": round(float(equity["equity"].iloc[-1]), 2),
        "sharpe": round(sharpe_ratio(returns), 3),
        "sortino": round(sortino_ratio(returns), 3),
        "max_drawdown": round(max_drawdown(equity["equity"]), 3),
        "win_rate": round(win_rate(all_trades), 3),
        "profit_factor": round(profit_factor(all_trades), 3),
        "trades": len(all_trades),
    }

    save_equity_curve(equity[["equity"]])
    save_performance_summary(summary)
    save_trade_log(all_trades)
    return summary
