def evaluate_signal_quality(symbol: str, score: float, governance_mode: str):
    setup = "A" if score >= 1.3 and governance_mode != "SAFE_MODE" else "B" if score >= 1.1 else "C"
    return {
        "symbol": symbol,
        "setup_quality": setup,
        "score": score,
        "tradable": setup in ["A", "B"],
    }


