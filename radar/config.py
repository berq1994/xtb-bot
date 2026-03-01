from dataclasses import dataclass, field
from typing import Dict, List
import os


@dataclass
class RadarConfig:
    timezone: str = "Europe/Prague"
    state_dir: str = ".state"

    alert_threshold_pct: float = 3.0
    news_per_ticker: int = 2
    top_n: int = 5

    fmp_api_key: str = os.getenv("FMPAPIKEY", "")

    benchmarks: Dict[str, str] = field(default_factory=lambda: {
        "spy": "SPY",
        "vix": "^VIX",
    })

    weights: Dict[str, float] = field(default_factory=lambda: {
        "momentum": 0.25,
        "volume": 0.20,
        "volatility": 0.15,
        "catalyst": 0.20,
        "market_regime": 0.20,
    })

    watchlist: List[str] = field(default_factory=lambda: [
        "SPY", "QQQ", "SMH", "XLE", "GLD"
    ])

    geopolitics_rss: List[str] = field(default_factory=lambda: [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ])


def load_config():
    return RadarConfig()