from ai.ticker_loader import load_all_tickers
from data_quality.ticker_registry import load_ticker_registry
from data_quality.source_resolver import is_enabled

def validate_startup_universe():
    reg = load_ticker_registry()
    tickers = load_all_tickers()

    mapped = []
    missing = []
    disabled = []

    for symbol in tickers:
        if symbol in reg:
            mapped.append(symbol)
            if not is_enabled(symbol):
                disabled.append(symbol)
        else:
            missing.append(symbol)

    return {
        "total": len(tickers),
        "mapped": mapped,
        "missing": missing,
        "disabled": disabled,
        "missing_ratio_pct": round((len(missing) / max(1, len(tickers))) * 100, 2),
    }
