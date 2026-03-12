from __future__ import annotations

from integrations.openbb_engine import generate_market_overview


def run_openbb_research(watchlist=None):
    overview = generate_market_overview(watchlist)
    lines = []
    lines.append("OPENBB / MARKET OVERVIEW")
    lines.append(f"Source: {overview['source']}")
    lines.append(f"Regime: {overview['regime']}")
    lines.append(f"Average move: {overview['average_change_pct']}%")
    lines.append("")
    lines.append("Leaders:")
    for row in overview['leaders']:
        lines.append(f"- {row['symbol']}: {row['change_pct']}% | trend {row['trend']} | price {row['price']}")
    lines.append("")
    lines.append("Laggards:")
    for row in overview['laggards']:
        lines.append(f"- {row['symbol']}: {row['change_pct']}% | trend {row['trend']} | price {row['price']}")
    return "\n".join(lines)
