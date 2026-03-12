from ai.sentiment_engine import score_text
from ai.regime_engine import classify_regime
from ai.volatility_engine import volatility_score

def combine_signal(row: dict, news_text: str = "", regime_inputs: dict | None = None) -> dict:
    regime_inputs = regime_inputs or {}
    sentiment = score_text(news_text)
    regime = classify_regime(
        spy_1d=regime_inputs.get("spy_1d", 0.0),
        qqq_1d=regime_inputs.get("qqq_1d", 0.0),
        vix=regime_inputs.get("vix", 18.0),
        btc_1d=regime_inputs.get("btc_1d", 0.0),
    )
    vol = volatility_score(row.get("hist_vol"), row.get("atr_pct"))

    momentum = float(row.get("momentum_score", 0.0))
    breakout = float(row.get("breakout_score", 0.0))
    mean_rev = float(row.get("mean_reversion_score", 0.0))

    final = (
        momentum * 0.28 +
        breakout * 0.24 +
        mean_rev * 0.12 +
        sentiment["score"] * 0.16 +
        (1 if regime["regime"] == "RISK_ON" else -1 if regime["regime"] == "RISK_OFF" else 0) * 0.10 +
        (100 - vol["score"]) / 100 * 0.10
    )
    return {
        "symbol": row.get("symbol"),
        "final_score": round(final, 3),
        "sentiment": sentiment,
        "regime": regime,
        "volatility": vol,
    }
