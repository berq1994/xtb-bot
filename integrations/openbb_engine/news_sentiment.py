from __future__ import annotations

from typing import Iterable, Dict, Any, List

DEFAULT_HEADLINES = {
    "NVDA": [
        "AI demand remains strong across data center cycle",
        "Semiconductor leadership supports momentum",
    ],
    "AAPL": [
        "Consumer demand mixed ahead of product cycle",
        "Mega-cap quality still supports defensive interest",
    ],
    "MSFT": [
        "Cloud and AI narrative remains constructive",
        "Large-cap quality bid supports resilience",
    ],
    "TLT": [
        "Rates volatility pressures long duration bonds",
        "Defensive flow rises when growth slows",
    ],
    "BTC-USD": [
        "Crypto sentiment improves with risk appetite",
        "Volatility remains elevated across digital assets",
    ],
}

POSITIVE_WORDS = {
    "strong", "leadership", "supports", "constructive", "improves", "resilience", "quality", "demand", "bullish"
}
NEGATIVE_WORDS = {
    "mixed", "pressures", "volatility", "slows", "risk", "weakness", "bearish"
}


def build_news_sentiment(symbols: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for symbol in symbols:
        headlines = DEFAULT_HEADLINES.get(symbol, [
            f"{symbol} trading activity remains in focus",
            f"Market participants monitor {symbol} for follow-through",
        ])
        score = 0
        lower_lines: List[str] = [h.lower() for h in headlines]
        for line in lower_lines:
            score += sum(1 for w in POSITIVE_WORDS if w in line)
            score -= sum(1 for w in NEGATIVE_WORDS if w in line)
        if score >= 2:
            label = "positive"
        elif score <= -1:
            label = "negative"
        else:
            label = "neutral"
        result[symbol] = {
            "headlines": headlines,
            "sentiment_score": score,
            "sentiment_label": label,
            "source": "scaffold",
        }
    return result
