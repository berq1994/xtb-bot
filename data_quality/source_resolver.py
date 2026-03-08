from data_quality.ticker_registry import get_ticker_record

def resolve_symbol(symbol: str, source: str = "yahoo") -> str:
    rec = get_ticker_record(symbol)
    if not rec:
        return symbol
    return rec.get(source) or symbol

def report_name(symbol: str) -> str:
    rec = get_ticker_record(symbol)
    return rec.get("report") if rec else symbol

def is_enabled(symbol: str) -> bool:
    rec = get_ticker_record(symbol)
    if not rec:
        return True
    return bool(rec.get("enabled", True))
