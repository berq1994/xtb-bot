# radar/config.py
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml


def _env_first(*names: str, default: str = "") -> str:
    for n in names:
        v = os.getenv(n)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return default


def _as_list(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    # allow comma-separated
    s = str(v).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _as_dict(v) -> Dict[str, Any]:
    if isinstance(v, dict):
        return dict(v)
    return {}


@dataclass
class RadarConfig:
    # --- core ---
    timezone: str = "Europe/Prague"
    state_dir: str = ".state"

    # --- schedule times (HH:MM) ---
    premarket_time: str = "07:30"
    evening_time: str = "20:00"
    weekly_earnings_time: str = "08:00"  # Monday

    # --- alerts ---
    alert_start: str = "12:00"
    alert_end: str = "21:00"
    alert_threshold_pct: float = 3.0

    # --- limits ---
    news_per_ticker: int = 2
    top_n: int = 5

    # --- data / keys ---
    fmp_api_key: str = ""

    # --- universe ---
    benchmarks: Dict[str, str] = field(default_factory=lambda: {"spy": "SPY", "vix": "^VIX"})
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "momentum": 0.25,
            "rel_strength": 0.20,
            "volatility_volume": 0.15,
            "catalyst": 0.20,
            "market_regime": 0.20,
        }
    )

    # portfolio rows: {"ticker": "AAPL", "qty": 1, "entry": 123.4, ...}
    portfolio: List[Dict[str, Any]] = field(default_factory=list)

    watchlist: List[str] = field(default_factory=list)
    new_candidates: List[str] = field(default_factory=list)

    ticker_map: Dict[str, str] = field(default_factory=dict)

    # --- geopolitics/news sources ---
    geopolitics_rss: List[str] = field(default_factory=lambda: [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ])

    # --- notifications (mostly env-driven, kept here for convenience) ---
    telegram_token: str = ""
    telegram_chat_id: str = ""

    email_enabled: bool = False
    email_sender: str = ""
    email_receiver: str = ""
    gmail_password: str = ""


def load_config(path: Optional[str] = None) -> RadarConfig:
    """
    Loads config from YAML (default: ./config.yml or ENV CONFIG_PATH) and
    applies ENV overrides for secrets / tokens.

    Goal: be tolerant to partial configs — missing keys just fall back to defaults.
    """
    cfg = RadarConfig()

    cfg_path = path or _env_first("CONFIG_PATH", default="config.yml")
    data: Dict[str, Any] = {}
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                parsed = yaml.safe_load(f) or {}
                if isinstance(parsed, dict):
                    data = parsed
    except Exception:
        # keep defaults
        data = {}

    # basic
    cfg.timezone = str(data.get("timezone", cfg.timezone) or cfg.timezone).strip()
    cfg.state_dir = str(data.get("state_dir", cfg.state_dir) or cfg.state_dir).strip()

    # times
    cfg.premarket_time = str(data.get("premarket_time", cfg.premarket_time) or cfg.premarket_time).strip()
    cfg.evening_time = str(data.get("evening_time", cfg.evening_time) or cfg.evening_time).strip()
    cfg.weekly_earnings_time = str(data.get("weekly_earnings_time", cfg.weekly_earnings_time) or cfg.weekly_earnings_time).strip()

    # alerts
    cfg.alert_start = str(data.get("alert_start", cfg.alert_start) or cfg.alert_start).strip()
    cfg.alert_end = str(data.get("alert_end", cfg.alert_end) or cfg.alert_end).strip()
    try:
        cfg.alert_threshold_pct = float(data.get("alert_threshold_pct", cfg.alert_threshold_pct))
    except Exception:
        pass

    # limits
    try:
        cfg.news_per_ticker = int(data.get("news_per_ticker", cfg.news_per_ticker))
    except Exception:
        pass
    try:
        cfg.top_n = int(data.get("top_n", cfg.top_n))
    except Exception:
        pass

    # keys
    cfg.fmp_api_key = str(data.get("fmp_api_key", "") or "").strip()
    cfg.fmp_api_key = _env_first("FMPAPIKEY", "FMP_API_KEY", default=cfg.fmp_api_key)

    # universe
    cfg.benchmarks = {k: str(v).strip() for k, v in _as_dict(data.get("benchmarks")).items() if str(k).strip()}
    if not cfg.benchmarks:
        cfg.benchmarks = {"spy": "SPY", "vix": "^VIX"}

    w = _as_dict(data.get("weights"))
    if w:
        # keep only numeric values; tolerate strings like "0.2"
        out: Dict[str, float] = {}
        for k, v in w.items():
            try:
                out[str(k).strip()] = float(v)
            except Exception:
                continue
        if out:
            cfg.weights = out

    cfg.portfolio = []
    for row in (data.get("portfolio") or []):
        if isinstance(row, dict) and row.get("ticker"):
            cfg.portfolio.append(dict(row))

    cfg.watchlist = _as_list(data.get("watchlist"))
    cfg.new_candidates = _as_list(data.get("new_candidates"))

    tm = _as_dict(data.get("ticker_map"))
    cfg.ticker_map = {str(k).strip().upper(): str(v).strip() for k, v in tm.items() if str(k).strip()}

    cfg.geopolitics_rss = _as_list(data.get("geopolitics_rss")) or cfg.geopolitics_rss

    # env-only notification secrets (compat: old + new names)
    cfg.telegram_token = _env_first("TELEGRAMTOKEN", "TG_BOT_TOKEN", "TELEGRAM_TOKEN", default="")
    cfg.telegram_chat_id = _env_first("CHATID", "TG_CHAT_ID", "TELEGRAM_CHAT_ID", default="")

    email_enabled = _env_first("EMAIL_ENABLED", default="false").lower().strip()
    cfg.email_enabled = email_enabled in ("1", "true", "yes", "on")
    cfg.email_sender = _env_first("EMAIL_SENDER", default="")
    cfg.email_receiver = _env_first("EMAIL_RECEIVER", default="")
    cfg.gmail_password = _env_first("GMAILPASSWORD", "GMAIL_PASSWORD", default="")

    return cfg