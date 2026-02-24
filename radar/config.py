import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import yaml
except Exception:
    yaml = None


@dataclass
class RadarConfig:
    timezone: str
    state_dir: str

    # Times (local)
    premarket_time: str
    evening_time: str
    alert_start: str
    alert_end: str
    alert_threshold_pct: float

    # Data / scoring
    fmp_api_key: str
    news_per_ticker: int
    top_n: int

    # Telegram
    telegram_token: str
    telegram_chat_id: str

    # Email
    email_enabled: bool
    email_sender: str
    email_receiver: str
    gmail_password: str

    # Universe
    portfolio_rows: List[Dict[str, Any]]
    watchlist: List[str]
    new_candidates: List[str]
    ticker_map: Dict[str, str]

    # Weights
    weights: Dict[str, float]
    benchmark_spy: str


DEFAULT_CONFIG_PATHS = ["config.yml", "config.yaml", ".github/config.yml", ".github/config.yaml"]


def _load_yaml() -> Dict[str, Any]:
    if yaml is None:
        return {}
    path = None
    for p in DEFAULT_CONFIG_PATHS:
        if os.path.exists(p):
            path = p
            break
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _env(name: str, fallback: str = "") -> str:
    return (os.getenv(name) or fallback).strip()


def load_config() -> RadarConfig:
    cfg = _load_yaml()

    # ENV: podporujeme obě sady názvů (aby se ti nic nerozbilo)
    telegram_token = _env("TELEGRAMTOKEN", _env("TG_BOT_TOKEN"))
    telegram_chat_id = _env("CHATID", _env("TG_CHAT_ID"))

    fmp_api_key = _env("FMPAPIKEY", _env("FMP_API_KEY"))

    tz = _env("TIMEZONE", "Europe/Prague")

    premarket_time = _env("PREMARKET_TIME", "12:00")
    evening_time = _env("EVENING_TIME", "20:00")

    alert_start = _env("ALERT_START", "12:00")
    alert_end = _env("ALERT_END", "21:00")
    alert_threshold = float(_env("ALERT_THRESHOLD", "3") or "3")

    news_per = int(_env("NEWS_PER_TICKER", "2") or "2")
    top_n = int(_env("TOP_N", "5") or "5")

    email_enabled = (_env("EMAIL_ENABLED", "false").lower() == "true")
    email_sender = _env("EMAIL_SENDER")
    email_receiver = _env("EMAIL_RECEIVER")
    gmail_password = _env("GMAILPASSWORD")

    portfolio_rows = cfg.get("portfolio", []) if isinstance(cfg.get("portfolio"), list) else []
    watchlist = cfg.get("watchlist", []) if isinstance(cfg.get("watchlist"), list) else []
    new_candidates = cfg.get("new_candidates", []) if isinstance(cfg.get("new_candidates"), list) else []

    ticker_map = cfg.get("ticker_map", {}) if isinstance(cfg.get("ticker_map"), dict) else {}

    weights = cfg.get("weights", {}) if isinstance(cfg.get("weights"), dict) else {}
    # default weights
    w = {
        "momentum": float(weights.get("momentum", 0.25)),
        "rel_strength": float(weights.get("rel_strength", 0.20)),
        "volatility_volume": float(weights.get("volatility_volume", 0.15)),
        "catalyst": float(weights.get("catalyst", 0.20)),
        "market_regime": float(weights.get("market_regime", 0.20)),
    }
    s = sum(w.values()) or 1.0
    for k in w:
        w[k] = w[k] / s

    benchmark_spy = "SPY"
    if isinstance(cfg.get("benchmarks"), dict):
        benchmark_spy = str(cfg["benchmarks"].get("spy", "SPY")).strip() or "SPY"

    state_dir = ".state"

    return RadarConfig(
        timezone=tz,
        state_dir=state_dir,
        premarket_time=premarket_time,
        evening_time=evening_time,
        alert_start=alert_start,
        alert_end=alert_end,
        alert_threshold_pct=alert_threshold,
        fmp_api_key=fmp_api_key,
        news_per_ticker=news_per,
        top_n=top_n,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
        email_enabled=email_enabled,
        email_sender=email_sender,
        email_receiver=email_receiver,
        gmail_password=gmail_password,
        portfolio_rows=portfolio_rows,
        watchlist=[str(x).strip().upper() for x in watchlist if str(x).strip()],
        new_candidates=[str(x).strip().upper() for x in new_candidates if str(x).strip()],
        ticker_map={str(k).strip().upper(): str(v).strip() for k, v in ticker_map.items()},
        weights=w,
        benchmark_spy=benchmark_spy.strip().upper(),
    )