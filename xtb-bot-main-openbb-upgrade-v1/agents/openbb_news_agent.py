from __future__ import annotations

from integrations.openbb_engine import generate_market_overview, build_news_sentiment


def run_openbb_news(watchlist=None):
    overview = generate_market_overview(watchlist)
    symbols = [row["symbol"] for row in overview.get("leaders", []) + overview.get("laggards", [])]
    news_map = build_news_sentiment(symbols)

    lines = []
    lines.append("OPENBB NEWS / SENTIMENT")
    lines.append(f"Market regime: {overview.get('regime', 'mixed')}")
    lines.append("")
    for symbol in symbols:
        info = news_map[symbol]
        lines.append(f"{symbol}: {info['sentiment_label']} (score {info['sentiment_score']})")
        for headline in info["headlines"][:2]:
            lines.append(f"- {headline}")
        lines.append("")
    return "\n".join(lines).strip()
