from __future__ import annotations

from integrations.openbb_engine import generate_market_overview, build_news_sentiment
from cz_utils import regime_cs, sentiment_cs


def run_openbb_news(watchlist=None):
    overview = generate_market_overview(watchlist)
    symbols = [row["symbol"] for row in overview.get("leaders", []) + overview.get("laggards", [])]
    news_map = build_news_sentiment(symbols)

    lines = []
    lines.append("OPENBB ZPRÁVY / SENTIMENT")
    lines.append(f"Režim trhu: {regime_cs(overview.get('regime', 'mixed'))}")
    lines.append("")
    for symbol in symbols:
        info = news_map[symbol]
        lines.append(f"{symbol}: {sentiment_cs(info['sentiment_label'])} (skóre {info['sentiment_score']})")
        for headline in info["headlines"][:2]:
            lines.append(f"- {headline}")
        lines.append("")
    return "\n".join(lines).strip()\n