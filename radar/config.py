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
    s = str(v).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _as_dict(v) -> Dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _normalize_ticker_map(v: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}

    if isinstance(v, dict):
        for k, val in v.items():
            kk = str(k).strip().upper()
            vv = str(val).strip()
            if kk and vv:
                out[kk] = vv
        return out

    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        parts = [p.strip() for p in s.split(",") if p.strip()]
        for p in parts:
            if "=" in p:
                a, b = p.split("=", 1)
                kk = a.strip().upper()
                vv = b.strip()
                if kk and vv:
                    out[kk] = vv
        return out

    if isinstance(v, list):
        for item in v:
            if isinstance(item, str):
                s = item.strip()
                if "=" in s:
                    a, b = s.split("=", 1)
                    kk = a.strip().upper()
                    vv = b.strip()
                    if kk and vv:
                        out[kk] = vv
                continue

            if isinstance(item, dict):
                raw = item.get("from") or item.get("raw") or item.get("ticker")
                res = item.get("to") or item.get("resolved") or item.get("map_to")
                if raw is not None and res is not None:
                    kk = str(raw).strip().upper()
                    vv = str(res).strip()
                    if kk and vv:
                        out[kk] = vv
                continue

        return out

    return {}


@dataclass
class RadarConfig:
    timezone: str = "Europe/Prague"
    state_dir: str = ".state"

    premarket_time: str = "07:30"
    evening_time: str = "20:00"
    weekly_earnings_time: str = "08:00"

    alert_start: str = "12:00"
    alert_end: str = "21:00"
    alert_threshold_pct: float = 3.0

    news_per_ticker: int = 2
    top_n: int = 5

    fmp_api_key: str = ""

    benchmarks: Dict[str, str] = field(default_factory=lambda: {"spy": "SPY", "vix": "^VIX"})
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "momentum": 0.25,
            "volume": 0.20,
            "volatility": 0.15,
            "catalyst": 0.20,
            "market_regime": 0.20,
        }
    )

    watchlist: List[str] = field(default_factory=lambda: ["SPY", "QQQ", "SMH", "XLE", "GLD"])
    new_candidates: List[str] = field(default_factory=list)

    ticker_map: Dict[str, str] = field(default_factory=dict)

    geopolitics_rss: List[str] = field(default_factory=lambda: [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ])

    telegram_token: str = ""
    telegram_chat_id: str = ""

    email_enabled: bool = False
    email_sender: str = ""
    email_receiver: str = ""
    gmail_password: str = ""


def load_config(path: Optional[str] = None) -> RadarConfig:
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
        data = {}

    cfg.timezone = str(data.get("timezone", cfg.timezone) or cfg.timezone).strip()
    cfg.state_dir = str(data.get("state_dir", cfg.state_dir) or cfg.state_dir).strip()

    cfg.premarket_time = str(data.get("premarket_time", cfg.premarket_time) or cfg.premarket_time).strip()
    cfg.evening_time = str(data.get("evening_time", cfg.evening_time) or cfg.evening_time).strip()
    cfg.weekly_earnings_time = str(data.get("weekly_earnings_time", cfg.weekly_earnings_time) or cfg.weekly_earnings_time).strip()

    cfg.alert_start = str(data.get("alert_start", cfg.alert_start) or cfg.alert_start).strip()
    cfg.alert_end = str(data.get("alert_end", cfg.alert_end) or cfg.alert_end).strip()

    try:
        cfg.alert_threshold_pct = float(data.get("alert_threshold_pct", cfg.alert_threshold_pct))
    except Exception:
        pass

    try:
        cfg.news_per_ticker = int(data.get("news_per_ticker", cfg.news_per_ticker))
    except Exception:
        pass
    try:
        cfg.top_n = int(data.get("top_n", cfg.top_n))
    except Exception:
        pass

    cfg.fmp_api_key = str(data.get("fmp_api_key", "") or "").strip()
    # ✅ tvoje secrets: FMPAPIKEY
    cfg.fmp_api_key = _env_first("FMPAPIKEY", "FMP_API_KEY", default=cfg.fmp_api_key)

    bm = _as_dict(data.get("benchmarks"))
    if bm:
        cfg.benchmarks = {str(k).strip(): str(v).strip() for k, v in bm.items() if str(k).strip()}

    w = _as_dict(data.get("weights"))
    if w:
        out: Dict[str, float] = {}
        for k, v in w.items():
            try:
                out[str(k).strip()] = float(v)
            except Exception:
                continue
        if out:
            cfg.weights = out

    cfg.watchlist = _as_list(data.get("watchlist")) or cfg.watchlist
    cfg.new_candidates = _as_list(data.get("new_candidates"))

    cfg.ticker_map = _normalize_ticker_map(data.get("ticker_map"))

    cfg.geopolitics_rss = _as_list(data.get("geopolitics_rss")) or cfg.geopolitics_rss

    cfg.telegram_token = _env_first("TELEGRAMTOKEN", "TG_BOT_TOKEN", "TELEGRAM_TOKEN", default="")
    cfg.telegram_chat_id = _env_first("CHATID", "TG_CHAT_ID", "TELEGRAM_CHAT_ID", default="")

    email_enabled = _env_first("EMAIL_ENABLED", default="false").lower().strip()
    cfg.email_enabled = email_enabled in ("1", "true", "yes", "on")
    cfg.email_sender = _env_first("EMAIL_SENDER", default="")
    cfg.email_receiver = _env_first("EMAIL_RECEIVER", default="")
    # ✅ tvoje secrets: GMAILPASSWORD
    cfg.gmail_password = _env_first("GMAILPASSWORD", "GMAIL_PASSWORD", default="")

    return cfg