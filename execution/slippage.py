def estimate_slippage(order_size_usd: float, adv_usd: float):
    if adv_usd <= 0:
        return None
    return round((order_size_usd / adv_usd) * 10000, 2)
