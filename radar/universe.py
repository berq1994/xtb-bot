from typing import Dict, List, Tuple
from radar.config import RadarConfig

# ------------------------------------------------------------
# CELÁ JMÉNA FIREM / ETF
# ------------------------------------------------------------

TICKER_NAMES = {

    # --- Portfolio ---
    "NVDA": "NVIDIA",
    "TSM": "Taiwan Semiconductor Manufacturing",
    "MSFT": "Microsoft",
    "CVX": "Chevron",
    "CSG": "Czechoslovak Group",
    "SGLD": "iShares Physical Gold ETC",
    "NVO": "Novo Nordisk",
    "NBIS": "Nebius Group",
    "IREN": "Iris Energy",
    "LEU": "Centrus Energy",

    # --- Watchlist ---
    "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco QQQ Trust",
    "SMH": "VanEck Semiconductor ETF",

    # --- Kandidáti ---
    "ASML": "ASML Holding",
    "AMD": "Advanced Micro Devices",
    "AVGO": "Broadcom",
    "CRWD": "CrowdStrike",
    "LLT": "L3Harris Technologies",

    # --- Index / speciální ---
    "^VIX": "Volatility Index (VIX)",
}

# ------------------------------------------------------------
# LOGIKA TICKERŮ
# ------------------------------------------------------------

def resolve_ticker(raw: str, ticker_map: Dict[str, str]) -> str:
    t = (raw or "").strip().upper()
    return (ticker_map.get(t) or t).strip()


def resolve_name(ticker: str) -> str:
    return TICKER_NAMES.get(ticker, ticker)


def portfolio_tickers(cfg: RadarConfig) -> List[str]:
    out = []
    for row in cfg.portfolio_rows:
        if isinstance(row, dict) and row.get("ticker"):
            out.append(str(row["ticker"]).strip().upper())
    return out


def all_tickers(cfg: RadarConfig) -> List[str]:
    port = portfolio_tickers(cfg)
    wl = cfg.watchlist or []
    nc = cfg.new_candidates or []

    base = list(set(port + wl + nc + [cfg.benchmark_spy, "^VIX"]))
    return sorted([x for x in base if x])


def resolved_universe(cfg: RadarConfig) -> Tuple[List[str], Dict[str, str]]:
    raws = all_tickers(cfg)
    mapping = {t: resolve_ticker(t, cfg.ticker_map) for t in raws}
    resolved = sorted(set(mapping.values()))
    return resolved, mapping