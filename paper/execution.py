def build_order(symbol: str, price: float, score: float, size_pct: float):
    stop = round(price * 0.97, 4)
    target = round(price * 1.06, 4)
    if score < 0:
        stop = round(price * 1.03, 4)
        target = round(price * 0.94, 4)
    side = "LONG" if score >= 0 else "SHORT"
    return {
        "symbol": symbol,
        "side": side,
        "entry_price": round(price, 4),
        "stop": stop,
        "target": target,
        "size_pct": size_pct,
    }
