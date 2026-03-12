from __future__ import annotations

import json
from pathlib import Path

from integrations.openbb_engine import generate_market_overview

PORTFOLIO_PATH = Path("config/portfolio_state.json")
WATCHLIST_PATH = Path("config/watchlists/google_finance_watchlist.json")
OUTPUT_PATH = Path("intraday_levels.txt")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _portfolio_symbols_and_themes(data: dict) -> tuple[set[str], set[str]]:
    symbols: set[str] = set()
    themes: set[str] = set()
    for account in data.get("accounts", {}).values():
        for pos in account.get("positions", []):
            symbol = str(pos.get("symbol", "")).strip()
            if symbol:
                symbols.add(symbol)
            for theme in pos.get("theme", []):
                themes.add(str(theme))
    return symbols, themes


def _thematic_map() -> dict[str, set[str]]:
    return {
        "NVDA": {"semis", "ai"},
        "AMD": {"semis", "ai"},
        "TSM": {"semis", "ai", "foundry"},
        "MSFT": {"software", "cloud", "ai"},
        "GOOG": {"ai", "internet", "ads"},
        "GOOGL": {"ai", "internet", "ads"},
        "META": {"ai", "internet"},
        "PLTR": {"software", "data", "ai"},
        "PANW": {"cybersecurity", "software"},
        "S": {"cybersecurity", "software"},
        "NBIS": {"ai", "cloud", "infra"},
        "ORCL": {"software", "cloud"},
        "AMZN": {"cloud", "ai", "consumer"},
        "AAPL": {"consumer_tech"},
        "FCX": {"copper", "materials", "commodities"},
        "EQT": {"energy", "natural_gas"},
        "CVX": {"energy", "oil"},
        "LEU": {"uranium", "nuclear"},
        "FSLR": {"solar", "energy_transition"},
        "IREN": {"bitcoin", "energy", "ai_hpc"},
        "NVO": {"healthcare"},
        "GRMN": {"consumer_tech"},
        "CSG": {"defense", "industrial"},
        "SCCO": {"copper", "materials"},
        "IBIT": {"bitcoin", "crypto"},
        "BTC-USD": {"bitcoin", "crypto"},
        "BRK-B": {"financials", "conglomerate"},
        "BKNG": {"travel", "consumer"},
        "DPZ": {"consumer"},
        "COKE": {"consumer_defensive"},
        "CAG": {"consumer_defensive"},
        "INTC": {"semis"},
        "GEV": {"industrial", "energy_transition"},
        "TTD": {"ads", "software"},
        "AAOI": {"networking", "optics", "ai_infra"},
        "ONDS": {"drones", "industrial"},
        "CENX": {"materials", "aluminum"},
        "PYPL": {"fintech"},
        "NFLX": {"media"},
        "CVNA": {"consumer_cyclical"},
        "BDC": {"industrial"},
        "SNDK": {"storage", "semis"},
    }


def _overlap_note(symbol: str, portfolio_symbols: set[str], portfolio_themes: set[str]) -> tuple[float, str]:
    if symbol in portfolio_symbols:
        return 0.20, "uĹľ drĹľenĂˇ pozice"
    sym_themes = _thematic_map().get(symbol, set())
    overlap = sym_themes & portfolio_themes
    if {"ai", "semis"} & overlap:
        return 0.15, "vysokĂ© pĹ™ekrytĂ­ AI/semis"
    if {"energy", "oil", "natural_gas", "uranium", "solar", "commodities"} & overlap:
        return 0.08, "stĹ™ednĂ­ pĹ™ekrytĂ­ energy/komodity"
    if overlap:
        return 0.04, "mĂ­rnĂ© tematickĂ© pĹ™ekrytĂ­"
    return 0.0, "novĂ© tĂ©ma / diverzifikace"


def _levels(price: float, trend: str, penalty: float) -> dict:
    buy_pullback = round(price * (0.985 - penalty / 2), 2)
    buy_breakout = round(price * (1.008 + penalty / 3), 2)
    trim_above = round(price * (1.035 + penalty / 2), 2)
    stop_below = round(price * (0.972 - penalty / 2), 2)
    if trend == "down":
        buy_pullback = round(price * (0.97 - penalty / 3), 2)
        buy_breakout = round(price * (1.012 + penalty / 2), 2)
    return {
        "buy_pullback": buy_pullback,
        "buy_breakout": buy_breakout,
        "trim_above": trim_above,
        "stop_below": stop_below,
    }


def run_intraday_levels() -> str:
    portfolio = _load_json(PORTFOLIO_PATH)
    watchlist = _load_json(WATCHLIST_PATH).get("symbols", [])
    if not watchlist:
        return "INTRADAY LEVELS
ChybĂ­ config/watchlists/google_finance_watchlist.json"

    portfolio_symbols, portfolio_themes = _portfolio_symbols_and_themes(portfolio)
    overview = generate_market_overview(watchlist)
    rows = overview.get("symbols", [])

    lines = []
    lines.append("INTRADAY LEVELS")
    lines.append(f"ReĹľim trhu: {overview.get('regime', 'mixed')}")
    lines.append("")

    for row in rows:
        symbol = row.get("symbol", "")
        price = float(row.get("price", 0.0))
        trend = row.get("trend", "flat")
        penalty, note = _overlap_note(symbol, portfolio_symbols, portfolio_themes)
        levels = _levels(price, trend, penalty)
        lines.append(f"{symbol} | cena {price} | trend {trend}")
        lines.append(f"- koupit na pullbacku pod: {levels['buy_pullback']}")
        lines.append(f"- koupit breakout nad: {levels['buy_breakout']}")
        lines.append(f"- ÄŤĂˇsteÄŤnÄ› vybĂ­rat nad: {levels['trim_above']}")
        lines.append(f"- ochrannĂ˝ stop pod: {levels['stop_below']}")
        lines.append(f"- portfolio kontext: {note}")
        lines.append("")

    output = "\n".join(lines)".join(lines).strip()
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    return output




