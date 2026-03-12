from __future__ import annotations

from integrations.openbb_engine import build_news_sentiment, generate_market_overview
from cz_utils import regime_cs, sentiment_cs


def run_openbb_news(watchlist=None):
    overview = generate_market_overview(watchlist)
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])

    symbols = []
    for item in leaders[:3]:
        symbols.append(item["symbol"])
    for item in laggards[:3]:
        if item["symbol"] not in symbols:
            symbols.append(item["symbol"])

    news_map = build_news_sentiment(symbols)

    lines = []
    lines.append("OPENBB ZPRÁVY / SENTIMENT")
    lines.append(f"Režim trhu: {regime_cs(overview.get('regime', 'mixed'))}")
    lines.append("")

    if not symbols:
        lines.append("Žádné symboly k vyhodnocení.")
        return "\n".join(lines)

    for symbol in symbols:
        item = news_map.get(symbol, {})
        label = sentiment_cs(item.get("sentiment_label", "neutral"))
        score = item.get("sentiment_score", 0)
        lines.append(f"{symbol}: {label} (skóre {score})")

        reasons = item.get("reasons", [])
        if reasons:
            for reason in reasons[:2]:
                lines.append(f"- {reason}")
        else:
            lines.append("- Bez doplňujícího komentáře")

        lines.append("")

    return "\n".join(lines).strip()