def build_post_trade_review(symbol: str, planned_entry: list, actual_entry: float, pnl_usd: float, note: str):
    slippage = round(float(actual_entry) - float(sum(planned_entry) / len(planned_entry)), 4)
    verdict = "GOOD" if pnl_usd >= 0 else "LOSS_REVIEW"
    return {
        "symbol": symbol,
        "planned_entry_zone": planned_entry,
        "actual_entry": actual_entry,
        "pnl_usd": pnl_usd,
        "slippage_vs_plan": slippage,
        "verdict": verdict,
        "note": note,
    }
