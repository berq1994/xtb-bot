# radar/config.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml


_env_pat = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _sub_env(val: Any) -> Any:
    if isinstance(val, str):
        def repl(m):
            k = m.group(1)
            return os.getenv(k, "")
        return _env_pat.sub(repl, val)
    if isinstance(val, dict):
        return {k: _sub_env(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sub_env(v) for v in val]
    return val


@dataclass
class RadarConfig:
    fmp_api_key: str = ""
    timezone: str = "Europe/Prague"

    premarket_time: str = "12:00"
    evening_time: str = "20:00"

    alert_start: str = "12:00"
    alert_end: str = "21:00"
    alert_threshold_pct: float = 3.0

    news_per_ticker: int = 2
    top_n: int = 5
    earnings_days_ahead: int = 7

    benchmarks: Dict[str, str] = field(default_factory=lambda: {"spy": "SPY", "vix": "^VIX"})
    weights: Dict[str, float] = field(default_factory=dict)

    portfolio: List[Dict[str, Any]] = field(default_factory=list)
    watchlist: List[str] = field(default_factory=list)
    new_candidates: List[str] = field(default_factory=list)

    ticker_map: Dict[str, str] = field(default_factory=dict)

    state_dir: str = ".state"

    # runtime
    telegram_token: str = ""
    telegram_chat_id: str = ""

    email_enabled: bool = False
    email_sender: str = ""
    email_receiver: str = ""
    gmail_password: str = ""


def load_config(path: str = "config.yml") -> RadarConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    raw = _sub_env(raw)

    cfg = RadarConfig()
    for k, v in raw.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)

    # secrets/env
    cfg.telegram_token = (os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
    cfg.telegram_chat_id = str(os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or "").strip()

    cfg.email_enabled = (os.getenv("EMAIL_ENABLED", "false").strip().lower() == "true")
    cfg.email_sender = (os.getenv("EMAIL_SENDER") or "").strip()
    cfg.email_receiver = (os.getenv("EMAIL_RECEIVER") or "").strip()
    cfg.gmail_password = (os.getenv("GMAILPASSWORD") or "").strip()

    # FMP key – podporuj oba názvy
    if not cfg.fmp_api_key:
        cfg.fmp_api_key = (os.getenv("FMP_API_KEY") or os.getenv("FMPAPIKEY") or "").strip()

    return cfg