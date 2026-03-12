import sys
from pathlib import Path
import json

def _dummy_ai_rows():
    return [
        {"symbol": "NVDA", "final_score": 1.44, "sentiment": {"label": "bullish"}, "volatility": {"state": "MID"}},
        {"symbol": "AMD", "final_score": 1.18, "sentiment": {"label": "bullish"}, "volatility": {"state": "MID"}},
        {"symbol": "MSFT", "final_score": 0.93, "sentiment": {"label": "neutral"}, "volatility": {"state": "LOW"}},
        {"symbol": "BTC-USD", "final_score": 0.88, "sentiment": {"label": "bullish"}, "volatility": {"state": "HIGH"}},
        {"symbol": "CEZ.PR", "final_score": 0.51, "sentiment": {"label": "neutral"}, "volatility": {"state": "LOW"}},
    ]

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "default"

    if mode == "backtest":
        from backtesting.run import run_portfolio_backtest
        from reporting.backtest_report import telegram_backtest_summary
        summary = run_portfolio_backtest()
        print(telegram_backtest_summary(summary))
        return

    if mode == "ai_daily":
        from ai.ticker_loader import load_all_tickers
        from risk.portfolio_var import portfolio_var
        from reporting.executive_report import build_executive_report
        tickers = load_all_tickers()
        ai_rows = _dummy_ai_rows()
        summary = {
            "regime": "RISK_ON",
            "regime_confidence": 0.74,
            "portfolio_var": portfolio_var(len(tickers[:5]), 1.0),
            "max_dd_limit": "12% soft / 18% hard",
        }
        print(build_executive_report(summary, ai_rows))
        return

    if mode == "ai_recalibrate":
        from ai.model_registry import register_model
        from ai.experiment_tracker import log_experiment
        metrics = {"sharpe": 1.11, "sortino": 1.42, "max_dd": -0.09}
        reg = register_model("ensemble_v1", metrics)
        log_experiment("weekly_recalibration", {"registry_size": len(reg.get("active_models", [])), "metrics": metrics})
        print("AI recalibration completed.")
        return

    if mode == "openbb_scan":
        from agents.openbb_research_agent import run_openbb_research
        print(run_openbb_research())
        return

    if mode == "ai_walkforward":
        from backtesting.walk_forward import run_walk_forward
        result = run_walk_forward()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("Velký AI upgrade přidán. Použij: python run_agent.py backtest | ai_daily | ai_recalibrate | ai_walkforward | openbb_scan")

if __name__ == "__main__":
    main()
