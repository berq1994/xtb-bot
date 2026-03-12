from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


PORTFOLIO_PATH = Path("config/portfolio_state.json")
OUTPUT_PATH = Path("portfolio_context_report.txt")


def _load_portfolio() -> dict:
    if not PORTFOLIO_PATH.exists():
        return {}
    return json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))


def run_portfolio_context() -> str:
    data = _load_portfolio()
    if not data:
        return "PORTFOLIO CONTEXT\nSoubor config/portfolio_state.json nebyl nalezen."

    positions = []
    for account in data.get("accounts", {}).values():
        positions.extend(account.get("positions", []))

    currency = defaultdict(float)
    themes = Counter()
    symbols = []
    for row in positions:
        symbols.append(row.get("symbol", ""))
        currency[row.get("ccy", "N/A")] += float(row.get("value", 0.0))
        for theme in row.get("theme", []):
            themes[theme] += float(row.get("value", 0.0))

    lines = []
    lines.append("PORTFOLIO CONTEXT")
    lines.append(f"Počet pozic: {len(positions)}")
    lines.append("Měnová expozice:")
    for ccy, value in sorted(currency.items()):
        lines.append(f"- {ccy}: {round(value, 2)}")
    lines.append("Hlavní témata:")
    for theme, value in themes.most_common(10):
        lines.append(f"- {theme}: {round(value, 2)}")
    lines.append("Nejdůležitější risk flagy:")
    for flag in data.get("risk_flags", []):
        lines.append(f"- {flag}")
    lines.append("Použité override váhy:")
    for key, value in data.get("agent_overrides", {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("Sledované symboly v portfoliu:")
    lines.append(", ".join(sorted(set(filter(None, symbols)))))
    output = "\n".join(lines)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    return output
