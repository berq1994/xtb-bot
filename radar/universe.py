from typing import Dict, List, Tuple
from radar.config import RadarConfig


def resolve_ticker(raw: str, ticker_map: Dict[str, str]) -> str:
    t = (raw or "").strip().upper()
    return (ticker_map.get(t) or t).strip()


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
    # přidáme benchmark SPY a VIX (pro režim trhu)
    base = list(set(port + wl + nc + [cfg.benchmark_spy, "^VIX"]))
    return sorted([x for x in base if x])


def resolved_universe(cfg: RadarConfig) -> Tuple[List[str], Dict[str, str]]:
    """
    Vrací:
      - list tickers pro data source (po mapování)
      - map raw->resolved
    """
    raws = all_tickers(cfg)
    mapping = {t: resolve_ticker(t, cfg.ticker_map) for t in raws}
    resolved = sorted(set(mapping.values()))
    return resolved, mapping