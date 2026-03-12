from __future__ import annotations

from integrations.openbb_engine import generate_market_overview
from cz_utils import regime_cs, trend_cs


def run_openbb_research(watchlist=None):
    overview = generate_market_overview(watchlist)
    lines = []
    lines.append("OPENBB / PŘEHLED TRHU")
    lines.append(f"Zdroj dat: {overview['source']}")
    lines.append(f"Režim trhu: {regime_cs(overview['regime'])}")
    lines.append(f"Průměrný pohyb: {overview['average_change_pct']}%")
    lines.append("")
    lines.append("Nejsilnější tituly:")
    for row in overview['leaders']:
        lines.append(f"- {row['symbol']}: {row['change_pct']}% | trend {trend_cs(row['trend'])} | cena {row['price']}")
    lines.append("")
    lines.append("Nejslabší tituly:")
    for row in overview['laggards']:
        lines.append(f"- {row['symbol']}: {row['change_pct']}% | trend {trend_cs(row['trend'])} | cena {row['price']}")
    return "\n".join(lines)
