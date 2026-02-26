# radar/universe.py
from __future__ import annotations

from typing import Dict, List, Tuple, Optional
from radar.config import RadarConfig


def resolve_ticker(raw: str, ticker_map: Dict[str, str]) -> str:
    t = (raw or "").strip().upper()
    return (ticker_map.get(t) or t).strip()


def portfolio_tickers(cfg: RadarConfig) -> List[str]:
    out = []
    for row in cfg.portfolio:
        if isinstance(row, dict) and row.get("ticker"):
            out.append(str(row["ticker"]).strip().upper())
    return out


def all_tickers(cfg: RadarConfig) -> List[str]:
    port = portfolio_tickers(cfg)
    wl = [str(x).strip().upper() for x in (cfg.watchlist or []) if str(x).strip()]
    nc = [str(x).strip().upper() for x in (cfg.new_candidates or []) if str(x).strip()]
    base = list(set(port + wl + nc + [cfg.benchmarks.get("spy", "SPY"), cfg.benchmarks.get("vix", "^VIX")]))
    return sorted([x for x in base if x])


def resolved_universe(cfg: RadarConfig, universe: Optional[List[str]] = None) -> Tuple[List[str], Dict[str, str]]:
    """
    Vrací:
      - list tickers pro data source (po mapování)
      - map raw->resolved
    """
    raws = universe if universe else all_tickers(cfg)
    raws = [str(x).strip().upper() for x in raws if str(x).strip()]

    mapping = {t: resolve_ticker(t, cfg.ticker_map) for t in raws}
    resolved = sorted(set(mapping.values()))
    return resolved, mapping