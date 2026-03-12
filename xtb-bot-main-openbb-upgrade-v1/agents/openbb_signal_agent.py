from __future__ import annotations

from integrations.openbb_engine import generate_market_overview


def run_openbb_signal(watchlist=None):
    overview = generate_market_overview(watchlist)
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])
    leader = leaders[0] if leaders else None
    laggard = laggards[0] if laggards else None

    lines = []
    lines.append("OPENBB SIGNAL BUNDLE")
    lines.append(f"Market regime: {overview.get('regime', 'mixed')}")
    lines.append(f"Data source: {overview.get('source', 'fallback')}")
    lines.append("")

    if leader:
        lines.append("Primary long candidate:")
        lines.append(
            f"- {leader['symbol']} | move {leader['change_pct']}% | trend {leader['trend']} | price {leader['price']}"
        )
        lines.append("- Action: watch breakout / manual XTB confirmation")
        lines.append("")

    if laggard:
        lines.append("Primary weak candidate:")
        lines.append(
            f"- {laggard['symbol']} | move {laggard['change_pct']}% | trend {laggard['trend']} | price {laggard['price']}"
        )
        lines.append("- Action: watch weakness / hedge / avoid impulsive long")
        lines.append("")

    lines.append("Manual execution checklist:")
    lines.append("1. Confirm chart on XTB")
    lines.append("2. Confirm spread and volatility")
    lines.append("3. Set stop loss before entry")
    lines.append("4. Risk max 1% per trade")
    return "\n".join(lines)
