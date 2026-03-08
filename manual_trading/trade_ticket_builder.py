from manual_trading.entry_planner import plan_trade_levels
from manual_trading.risk_sizing import compute_position_size

def build_trade_ticket(symbol: str, score: float, last_price: float, direction: str, atr: float, risk_capital_usd: float):
    levels = plan_trade_levels(last_price=last_price, direction=direction, atr=atr)
    sizing = compute_position_size(
        entry_price=levels["entry_zone"][1] if direction == "LONG" else levels["entry_zone"][0],
        stop_price=levels["stop_loss"],
        risk_capital_usd=risk_capital_usd,
    )

    rr1 = 0.0
    rr2 = 0.0
    entry_ref = levels["entry_zone"][1] if direction == "LONG" else levels["entry_zone"][0]
    risk = abs(entry_ref - levels["stop_loss"])
    if risk > 0:
        rr1 = abs(levels["take_profit_1"] - entry_ref) / risk
        rr2 = abs(levels["take_profit_2"] - entry_ref) / risk

    return {
        "symbol": symbol,
        "direction": direction,
        "signal_score": score,
        "entry_zone": levels["entry_zone"],
        "stop_loss": levels["stop_loss"],
        "take_profit_1": levels["take_profit_1"],
        "take_profit_2": levels["take_profit_2"],
        "rr_tp1": round(rr1, 2),
        "rr_tp2": round(rr2, 2),
        "risk_sizing": sizing,
        "xtb_manual_note": "Zadat ručně do xStation jako MARKET nebo LIMIT dle situace.",
    }
