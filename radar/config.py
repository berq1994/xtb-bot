from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class RadarConfig:
    timezone: str = "Europe/Prague"
    state_dir: str = ".state"

    fmp_api_key: str = ""
    news_per_ticker: int = 2
    additional_news_rss: List[str] = field(default_factory=lambda: ["https://seekingalpha.com/feed.xml"])

    benchmarks: Dict[str, str] = field(default_factory=lambda: {"spy": "SPY", "vix": "^VIX"})
    universe: List[str] = field(default_factory=list)
    ticker_map: Dict[str, str] = field(default_factory=dict)

    top_n: int = 5
    alert_threshold_pct: float = 3.0

    email_enabled: bool = False
    email_sender: str = ""
    email_receiver: str = ""
    gmail_password: str = ""

    geopolitics_rss: List[str] = field(default_factory=list)
    geopolitics_source_weight: Dict[str, float] = field(default_factory=dict)

    portfolio_snapshot_path: str = "portfolio_snapshot/portfolio.yml"

    daytrade: Dict[str, Any] = field(default_factory=dict)


def _read_yaml(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_config(path: str = "config.yml") -> RadarConfig:
    data = _read_yaml(path)

    cfg = RadarConfig()

    cfg.timezone = str(data.get("timezone") or cfg.timezone)
    cfg.state_dir = str(data.get("state_dir") or cfg.state_dir)

    cfg.fmp_api_key = str(os.getenv("FMPAPIKEY") or os.getenv("FMP_API_KEY") or data.get("fmp_api_key") or cfg.fmp_api_key)
    cfg.news_per_ticker = int(data.get("news_per_ticker") or cfg.news_per_ticker)
    cfg.additional_news_rss = data.get("additional_news_rss") or cfg.additional_news_rss

    cfg.benchmarks = data.get("benchmarks") or cfg.benchmarks
    cfg.universe = data.get("universe") or cfg.universe
    cfg.ticker_map = data.get("ticker_map") or cfg.ticker_map

    cfg.top_n = int(data.get("top_n") or cfg.top_n)
    cfg.alert_threshold_pct = float(data.get("alert_threshold_pct") or cfg.alert_threshold_pct)

    cfg.email_enabled = bool(str(os.getenv("EMAIL_ENABLED") or data.get("email_enabled") or "false").lower() == "true")
    cfg.email_sender = str(os.getenv("EMAIL_SENDER") or data.get("email_sender") or cfg.email_sender)
    cfg.email_receiver = str(os.getenv("EMAIL_RECEIVER") or data.get("email_receiver") or cfg.email_receiver)
    cfg.gmail_password = str(os.getenv("GMAILPASSWORD") or data.get("gmail_password") or cfg.gmail_password)

    cfg.geopolitics_rss = data.get("geopolitics_rss") or cfg.geopolitics_rss
    cfg.geopolitics_source_weight = data.get("geopolitics_source_weight") or cfg.geopolitics_source_weight

    cfg.portfolio_snapshot_path = str(
        os.getenv("PORTFOLIO_SNAPSHOT_PATH") or data.get("portfolio_snapshot_path") or cfg.portfolio_snapshot_path
    )

    cfg.daytrade = data.get("daytrade") or cfg.daytrade

    return cfg