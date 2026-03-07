from datetime import datetime
from .execution import build_order
from .portfolio import load_trade_log, save_trade_log, load_equity, save_equity
from time_utils.market_hours import is_symbol_tradeable

def process_signals(signals: list, now=None, btc_mode="market_hours_only"):
    now = now or datetime.utcnow()
    log = load_trade_log()
    equity = load_equity()
    for sig in signals:
        symbol = sig["symbol"]
        if not is_symbol_tradeable(symbol, now=now, btc_mode=btc_mode):
            continue
        if not sig.get("allowed", False):
            continue
        if any(p["symbol"] == symbol for p in log["open"]):
            continue
        price = float(sig.get("last_price", 100.0))
        order = build_order(symbol, price, sig["composite_score"], sig["position_size_pct"])
        order.update({
            "opened_at": now.isoformat(),
            "model": sig["setup"],
            "regime": sig["regime"],
        })
        log["open"].append(order)
    save_trade_log(log)
    equity["curve"].append({"ts": now.isoformat(), "equity": equity["equity"]})
    save_equity(equity)
    return log, equity
