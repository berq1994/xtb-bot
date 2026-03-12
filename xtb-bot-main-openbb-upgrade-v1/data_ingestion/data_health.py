from data_quality.quality_score import compute_quality_score, quality_label
from data_ingestion.ticker_normalizer import normalize_symbol

def health_snapshot(symbol: str, has_price=True, has_volume=True, source_ok=True, stale=False):
    norm = normalize_symbol(symbol, "yahoo")
    score = compute_quality_score(
        has_price=has_price,
        has_volume=has_volume,
        source_ok=source_ok,
        stale=stale,
        mapped=norm["resolved"] != symbol or norm["input"] == symbol,
    )
    return {
        "symbol": symbol,
        "resolved": norm["resolved"],
        "report": norm["report"],
        "enabled": norm["enabled"],
        "quality_score": score,
        "quality_label": quality_label(score),
    }
