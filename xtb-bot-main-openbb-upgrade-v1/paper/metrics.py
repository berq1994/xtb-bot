def summarize(log: dict, equity: dict):
    open_n = len(log.get("open", []))
    closed_n = len(log.get("closed", []))
    eq = float(equity.get("equity", 0.0))
    return {"open": open_n, "closed": closed_n, "equity": eq}
