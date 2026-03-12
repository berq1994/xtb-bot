def telegram_backtest_summary(summary: dict) -> str:
    return (
        "📊 <b>RADAR G BACKTEST</b>\n"
        f"Tickery: <b>{len(summary.get('tickers', []))}</b>\n"
        f"Final equity: <b>{summary.get('final_equity')}</b>\n"
        f"Sharpe: <b>{summary.get('sharpe')}</b>\n"
        f"Sortino: <b>{summary.get('sortino')}</b>\n"
        f"Max DD: <b>{summary.get('max_drawdown')}</b>\n"
        f"Win rate: <b>{summary.get('win_rate')}</b>\n"
        f"Profit factor: <b>{summary.get('profit_factor')}</b>\n"
        f"Počet obchodů: <b>{summary.get('trades')}</b>"
    )
