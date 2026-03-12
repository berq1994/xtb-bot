def run_post_trade_review_agent(symbol: str, pnl_usd: float):
    return {
        "symbol": symbol,
        "pnl_usd": pnl_usd,
        "review": "GOOD" if pnl_usd >= 0 else "LOSS_REVIEW",
    }


