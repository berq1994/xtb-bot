from __future__ import annotations

from integrations.openbb_engine import generate_market_overview
from cz_utils import regime_cs, trend_cs


def run_openbb_signal(watchlist=None):
    overview = generate_market_overview(watchlist)
    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])
    leader = leaders[0] if leaders else None
    laggard = laggards[0] if laggards else None

    lines = []
    lines.append("OPENBB SIGNĂLOVĂť BALĂŤÄŚEK")
    lines.append(f"ReĹľim trhu: {regime_cs(overview.get('regime', 'mixed'))}")
    lines.append(f"Zdroj dat: {overview.get('source', 'fallback')}")
    lines.append("")

    if leader:
        lines.append("HlavnĂ­ kandidĂˇt na long:")
        lines.append(
            f"- {leader['symbol']} | pohyb {leader['change_pct']}% | trend {trend_cs(leader['trend'])} | cena {leader['price']}"
        )
        lines.append("- Akce: sledovat breakout / ruÄŤnĂ­ potvrzenĂ­ v XTB")
        lines.append("")

    if laggard:
        lines.append("HlavnĂ­ slabĂ˝ kandidĂˇt:")
        lines.append(
            f"- {laggard['symbol']} | pohyb {laggard['change_pct']}% | trend {trend_cs(laggard['trend'])} | cena {laggard['price']}"
        )
        lines.append("- Akce: sledovat slabost / hedge / nebrat impulzivnĂ­ long")
        lines.append("")

    lines.append("KontrolnĂ­ seznam pro ruÄŤnĂ­ vstup:")
    lines.append("1. Potvrdit graf v XTB")
    lines.append("2. Potvrdit spread a volatilitu")
    lines.append("3. Nastavit stop loss jeĹˇtÄ› pĹ™ed vstupem")
    lines.append("4. Riziko max. 1 % na obchod")
    return "\\n".join(lines)
