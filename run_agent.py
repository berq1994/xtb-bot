import sys

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "default"

    if mode == "backtest":
        from backtesting.run import run_portfolio_backtest
        from reporting.backtest_report import telegram_backtest_summary
        summary = run_portfolio_backtest()
        print(telegram_backtest_summary(summary))
        return

    print("Radar G upgrade přidán. Použij: python run_agent.py backtest")

if __name__ == "__main__":
    main()
