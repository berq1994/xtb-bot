import random

def build_snapshot(symbol: str) -> dict:
    move_1d = round(random.uniform(-4.5, 4.5), 2)
    move_5d = round(random.uniform(-9.0, 9.0), 2)
    vol = round(random.uniform(0.8, 3.5), 2)
    rsi = round(random.uniform(20, 80), 1)
    breakout = random.random() > 0.78
    price = round(random.uniform(20, 500), 2)
    return {
        "symbol": symbol,
        "last_price": price,
        "move_1d_pct": move_1d,
        "move_5d_pct": move_5d,
        "volume_spike": vol,
        "rsi_14": rsi,
        "breakout_20d": breakout,
        "close_vs_20d_high_pct": round(random.uniform(-0.05, 0.03), 4),
        "volatility_pct": abs(move_1d),
    }
