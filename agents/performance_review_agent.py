from __future__ import annotations

import json
from pathlib import Path

from agents.signal_history_agent import HISTORY_PATH
from cz_utils import regime_cs, decision_cs

REVIEW_PATH = Path("data/phase5_performance_review.txt")


def run_performance_review(limit: int = 20) -> str:
    rows: list[dict] = []
    if HISTORY_PATH.exists():
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    rows = rows[-limit:]

    symbols: dict[str, int] = {}
    regimes: dict[str, int] = {}
    decisions: dict[str, int] = {}
    for row in rows:
        ticket = row.get("ticket") or {}
        symbol = ticket.get("symbol", "NONE")
        symbols[symbol] = symbols.get(symbol, 0) + 1
        regime = row.get("regime", "mixed")
        regimes[regime] = regimes.get(regime, 0) + 1
        decision = row.get("supervisor", {}).get("decision", "wait")
        decisions[decision] = decisions.get(decision, 0) + 1

    top_symbol = max(symbols, key=symbols.get) if symbols else "NONE"
    lines = []
    lines.append("PŘEHLED VÝKONNOSTI – FÁZE 5")
    lines.append(f"Vyhodnocené vzorky: {len(rows)}")
    lines.append(f"Nejčastější symbol ticketu: {top_symbol}")
    lines.append("Režimy:")
    for key, value in regimes.items():
        lines.append(f"- {regime_cs(key)}: {value}")
    lines.append("Rozhodnutí:")
    for key, value in decisions.items():
        lines.append(f"- {decision_cs(key)}: {value}")
    lines.append("Symboly:")
    for key, value in symbols.items():
        lines.append(f"- {key}: {value}")
    output = "\n".join(lines)
    REVIEW_PATH.write_text(output, encoding="utf-8")
    return output