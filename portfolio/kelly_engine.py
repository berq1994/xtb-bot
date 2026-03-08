def kelly_fraction(edge: float, odds: float):
    if odds <= 0:
        return 0.0
    return max(0.0, min(0.25, (edge / odds)))
