from __future__ import annotations

from pathlib import Path

from integrations.openbb_engine import generate_market_overview
from agents.xtb_manual_ticket_agent import run_xtb_manual_ticket

OUTPUT_PATH = Path("fmp_levels.txt")


def _levels(price: float, trend: str) -> dict:
    if trend == "up":
        return {
            "buy_under": round(price * 0.992, 2),
            "breakout_above": round(price * 1.008, 2),
            "trim_above": round(price * 1.03, 2),
            "hard_stop": round(price * 0.978, 2),
        }
    return {
        "buy_under": round(price * 0.985, 2),
        "breakout_above": round(price * 1.012, 2),
        "trim_above": round(price * 1.02, 2),
        "hard_stop": round(price * 0.97, 2),
    }


def run_fmp_levels(watchlist=None) -> str:
    overview = generate_market_overview(watchlist)
    rows = overview.get("symbols", [])[:10]
    lines = []
    lines.append("TRŽNÍ LEVELY")
    lines.append(f"Zdroj dat: {overview.get('source', 'unknown')}")
    lines.append(f"Režim trhu: {overview.get('regime', 'mixed')}")
    lines.append("")
    for row in rows:
        px = float(row.get('price', 0.0))
        lv = _levels(px, row.get('trend', 'flat'))
        lines.append(f"{row.get('symbol')} | cena {px} | trend {row.get('trend')}")
        lines.append(f"- koupit pod: {lv['buy_under']}")
        lines.append(f"- breakout nad: {lv['breakout_above']}")
        lines.append(f"- trim nad: {lv['trim_above']}")
        lines.append(f"- stop: {lv['hard_stop']}")
        lines.append("")
    lines.append(run_xtb_manual_ticket(watchlist))
    output = "\n".join(lines).strip()
    OUTPUT_PATH.write_text(output, encoding='utf-8')
    return output
