def movement_class(pct_1d: float | None) -> str:
    """
    Klasifikace denního pohybu podle % změny.
    Používá se pro 'label' v reportu / analýze.
    """
    if pct_1d is None:
        return "NO_DATA"

    x = float(pct_1d)

    # prahy můžeš později dát do configu, zatím natvrdo (rozumné defaulty)
    if x >= 8.0:
        return "MOONSHOT_UP"
    if x >= 3.0:
        return "STRONG_UP"
    if x >= 1.0:
        return "UP"
    if x > -1.0:
        return "FLAT"
    if x > -3.0:
        return "DOWN"
    if x > -8.0:
        return "STRONG_DOWN"
    return "CRASH_DOWN"