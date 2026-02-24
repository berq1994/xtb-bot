from dataclasses import dataclass
from typing import List, Optional, Tuple

from radar.data_sources import combined_news

WHY_KEYWORDS = [
    (["earnings", "results", "quarter", "beat", "miss"], "výsledky (earnings) / překvapení vs očekávání"),
    (["guidance", "outlook", "forecast", "raises", "cuts"], "výhled (guidance) / změna očekávání"),
    (["upgrade", "downgrade", "price target", "rating"], "analytické doporučení (upgrade/downgrade/cílová cena)"),
    (["acquire", "acquisition", "merger", "deal"], "akvizice / fúze / transakce"),
    (["sec", "investigation", "lawsuit", "regulator", "antitrust"], "regulace / vyšetřování / právní zprávy"),
    (["contract", "partnership", "orders"], "zakázky / partnerství / objednávky"),
    (["chip", "ai", "gpu", "data center", "semiconductor"], "AI/čipy – sektorové zprávy"),
    (["dividend", "buyback", "repurchase"], "dividenda / buyback"),
]


def why_from_headlines(news_items) -> str:
    if not news_items:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    titles = " ".join([t for (_, t, _) in news_items]).lower()
    hits = []
    for keys, reason in WHY_KEYWORDS:
        if any(k in titles for k in keys):
            hits.append(reason)
    if not hits:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    return "; ".join(hits[:2]) + "."


def movement_class(pct: Optional[float], vol_ratio: float, thr: float = 3.0) -> str:
    """
    Klasifikace pohybu:
      >= +thr : SILNÝ RŮST
      +1..+thr : RŮST
      -1..+1 : NEUTRÁL
      -thr..-1 : POKLES
      <= -thr : SILNÝ POKLES
    + štítek na objemu
    """
    if pct is None:
        return "NEZNÁMÉ"
    label = "NEUTRÁL"
    if pct >= thr:
        label = "SILNÝ RŮST"
    elif pct >= 1.0:
        label = "RŮST"
    elif pct <= -thr:
        label = "SILNÝ POKLES"
    elif pct <= -1.0:
        label = "POKLES"

    if vol_ratio >= 2.0 and label != "NEZNÁMÉ":
        label += " (na objemu)"
    return label