# radar/features.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# Klasifikace pohybu (1D %)
# ============================================================
def movement_class(pct_1d: Optional[float]) -> str:
    """
    Klasifikace denního pohybu podle % změny.
    Vrací stabilní "label" použitelné v reportingu.
    """
    if pct_1d is None:
        return "NO_DATA"

    x = float(pct_1d)

    if x >= 8.0:
        return "MOONSHOT_UP"
    if x >= 3.0:
        return "STRONG_UP"
    if x >= 1.0:
        return "UP"
    if x > -1.0:
        return "FLAT"
    if x > -3.0:
        return "DOWN"
    if x > -8.0:
        return "STRONG_DOWN"
    return "CRASH_DOWN"


# ============================================================
# Interpretace headlines -> "proč se to hýbe"
# (lehké heuristiky, profesionální styl: jen indikace, ne jistota)
# ============================================================
WHY_KEYWORDS: List[Tuple[List[str], str]] = [
    (["earnings", "results", "quarter", "beat", "miss"], "výsledky (earnings) / překvapení vs očekávání"),
    (["guidance", "outlook", "forecast", "raises", "cuts"], "výhled (guidance) / změna očekávání"),
    (["upgrade", "downgrade", "price target", "rating"], "analytické doporučení (upgrade/downgrade/cílová cena)"),
    (["acquire", "acquisition", "merger", "deal"], "akvizice / fúze / transakce"),
    (["sec", "investigation", "lawsuit", "regulator", "antitrust"], "regulace / vyšetřování / právní zprávy"),
    (["contract", "partnership", "orders"], "zakázky / partnerství / objednávky"),
    (["chip", "ai", "gpu", "data center", "semiconductor"], "AI/čipy – sektorové zprávy"),
    (["dividend", "buyback", "repurchase"], "dividenda / buyback"),
]


def why_from_headlines(news_items: List[Tuple[str, str, str]]) -> str:
    """
    news_items: [(src, title, link), ...]
    """
    if not news_items:
        return "bez jasné zprávy – může to být sentiment/technika/trh."

    titles = " ".join([t for (_, t, _) in news_items]).lower()
    hits: List[str] = []
    for keys, reason in WHY_KEYWORDS:
        if any(k in titles for k in keys):
            hits.append(reason)

    if not hits:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    return "; ".join(hits[:2]) + "."


# ============================================================
# compute_features – tohle ti chybělo (ImportError)
# ============================================================
def compute_features(ticker: str, cfg: Dict[str, Any], bench: str = "SPY") -> Dict[str, Any]:
    """
    Vypočítá feature set pro scoring.
    Vrací dict, který engine/scoring/reporting používá.

    Pozn.: importy dáváme dovnitř funkce, aby se to nezacyklilo
    a aby se to nerozbilo, pokud ještě ladíš data_sources.
    """
    # lazy imports (kvůli stabilitě)
    try:
        from radar.data_sources import (
            get_price_data,
            get_rel_strength_5d,
            get_volume_ratio,
            combined_news,
            days_to_earnings,
        )
    except Exception:
        # Když ještě data_sources nemáš hotové, bot aspoň nespadne na importu
        def get_price_data(_t: str, _cfg: Dict[str, Any]) -> Dict[str, Any]:
            return {"ticker": _t, "src": "—", "pct_1d": None, "last": None, "prev": None}

        def get_rel_strength_5d(_t: str, _bench: str = "SPY") -> Optional[float]:
            return None

        def get_volume_ratio(_t: str) -> float:
            return 1.0

        def combined_news(_t: str, _limit_each: int = 2) -> List[Tuple[str, str, str]]:
            return []

        def days_to_earnings(_t: str, _cfg: Dict[str, Any]) -> Optional[int]:
            return None

    # --- prices
    px = get_price_data(ticker, cfg)
    pct_1d = px.get("pct_1d")

    # --- movement label
    mv = movement_class(pct_1d)

    # --- relative strength
    rs_5d = get_rel_strength_5d(ticker, bench=bench)

    # --- volume ratio
    vol_ratio = get_volume_ratio(ticker)

    # --- news
    news_per = int(cfg.get("NEWS_PER_TICKER", cfg.get("news_per_ticker", 2)) or 2)
    news_items = combined_news(ticker, limit_each=news_per)
    why = why_from_headlines(news_items)

    # --- earnings proximity (pokud je FMP)
    dte = days_to_earnings(ticker, cfg)

    return {
        "ticker": ticker,
        "src": px.get("src", "—"),
        "last": px.get("last"),
        "prev": px.get("prev"),
        "pct_1d": pct_1d,
        "movement": mv,            # <= tohle chceš
        "rs_5d": rs_5d,
        "vol_ratio": vol_ratio,
        "news": news_items,
        "why": why,
        "days_to_earnings": dte,
    }