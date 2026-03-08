def plan_trade_levels(last_price: float, direction: str = "LONG", atr: float = 1.5):
    last_price = float(last_price)
    atr = float(atr)

    if direction == "SHORT":
        entry_zone = [round(last_price * 0.998, 2), round(last_price * 1.002, 2)]
        stop = round(last_price + atr * 1.2, 2)
        tp1 = round(last_price - atr * 1.5, 2)
        tp2 = round(last_price - atr * 2.5, 2)
    else:
        entry_zone = [round(last_price * 0.998, 2), round(last_price * 1.002, 2)]
        stop = round(last_price - atr * 1.2, 2)
        tp1 = round(last_price + atr * 1.5, 2)
        tp2 = round(last_price + atr * 2.5, 2)

    return {
        "entry_zone": entry_zone,
        "stop_loss": stop,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
    }
