from data_quality.source_resolver import resolve_symbol, report_name, is_enabled

def normalize_symbol(symbol: str, source: str = "yahoo") -> dict:
    return {
        "input": symbol,
        "resolved": resolve_symbol(symbol, source),
        "report": report_name(symbol),
        "enabled": is_enabled(symbol),
        "source": source,
    }
