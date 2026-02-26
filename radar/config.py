# radar/config.py
from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

try:
    import yaml
except Exception:
    yaml = None


@dataclass
class RadarConfig:
    # core
    timezone: str = "Europe/Prague"
    state_dir: str = ".state"

    # schedule
    premarket_time: str = "07:30"
    evening_time: str = "20:00"
    alert_start: str = "12:00"
    alert_end: str = "21:00"
    weekly_earnings_time: str = "08:00"  # pondělí

    # thresholds
    alert_threshold_pct: float = 3.0

    # limits
    news_per_ticker: int = 2
    top_n: int = 5

    # keys
    fmp_api_key: str = ""

    # sets
    benchmarks: Dict[str, str] = field(default_factory=lambda: {"spy": "SPY", "vix": "^VIX"})
    weights: Dict[str, float] = field(default_factory=lambda: {
        "momentum": 0.25,
        "rel_strength": 0.20,
        "volatility_volume": 0.15,
        "catalyst": 0.20,
        "market_regime": 0.20,
    })

    portfolio: List[Dict[str, Any]] = field(default_factory=list)
    watchlist: List[str] = field(default_factory=lambda: ["SPY", "QQQ", "SMH"])
    new_candidates: List[str] = field(default_factory=list)

    # mapping raw->yahoo
    ticker_map: Dict[str, str] = field(default_factory=dict)


# ----------------------------
# YAML + helpers
# ----------------------------
def _load_yaml() -> Dict[str, Any]:
    if yaml is None:
        return {}
    for p in ("config.yml", "config.yaml"):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
    return {}


def _as_list_str(x) -> List[str]:
    if not isinstance(x, list):
        return []
    out = []
    for it in x:
        s = str(it).strip()
        if s:
            out.append(s)
    return out


def _normalize_weights(w: Dict[str, float]) -> Dict[str, float]:
    # ohlídáme jen validní čísla
    clean: Dict[str, float] = {}
    for k, v in (w or {}).items():
        try:
            clean[str(k).strip()] = float(v)
        except Exception:
            pass

    s = sum(clean.values())
    if s > 0:
        for k in list(clean.keys()):
            clean[k] = clean[k] / s
    return clean


def _read_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _load_learned_weights(state_dir: str) -> Dict[str, float]:
    """
    Načte learned váhy z .state/learned_weights.json, pokud existují.
    Vrací normalizované váhy (nebo {}).
    """
    if not state_dir:
        state_dir = ".state"
    path = os.path.join(state_dir, "learned_weights.json")
    data = _read_json(path, {})
    if not isinstance(data, dict):
        return {}
    w = _normalize_weights(data)
    # musí mít alespoň jeden relevantní klíč, jinak ignorujeme
    wanted = {"momentum", "rel_strength", "volatility_volume", "catalyst", "market_regime"}
    if not any(k in w for k in wanted):
        return {}
    # udrž jen známé klíče (aby se tam nedostalo něco navíc)
    return {k: w[k] for k in w if k in wanted}


# ----------------------------
# public
# ----------------------------
def load_config() -> RadarConfig:
    raw = _load_yaml()
    cfg = RadarConfig()

    # yaml -> cfg
    cfg.timezone = str(raw.get("timezone", cfg.timezone)).strip()
    cfg.state_dir = str(raw.get("state_dir", cfg.state_dir)).strip()

    cfg.premarket_time = str(raw.get("premarket_time", cfg.premarket_time)).strip()
    cfg.evening_time = str(raw.get("evening_time", cfg.evening_time)).strip()
    cfg.alert_start = str(raw.get("alert_start", cfg.alert_start)).strip()
    cfg.alert_end = str(raw.get("alert_end", cfg.alert_end)).strip()
    cfg.weekly_earnings_time = str(raw.get("weekly_earnings_time", cfg.weekly_earnings_time)).strip()

    cfg.alert_threshold_pct = float(raw.get("alert_threshold_pct", cfg.alert_threshold_pct) or cfg.alert_threshold_pct)
    cfg.news_per_ticker = int(raw.get("news_per_ticker", cfg.news_per_ticker) or cfg.news_per_ticker)
    cfg.top_n = int(raw.get("top_n", cfg.top_n) or cfg.top_n)

    cfg.fmp_api_key = str(raw.get("fmp_api_key", "") or "").strip()
    # env override (funguje i s vašimi secret názvy)
    cfg.fmp_api_key = (os.getenv("FMPAPIKEY") or os.getenv("FMP_API_KEY") or cfg.fmp_api_key).strip()

    # benchmarks
    if isinstance(raw.get("benchmarks"), dict):
        cfg.benchmarks.update({str(k).strip(): str(v).strip() for k, v in raw["benchmarks"].items()})

    # weights z YAML
    if isinstance(raw.get("weights"), dict):
        w_yaml: Dict[str, float] = {}
        for k, v in raw["weights"].items():
            try:
                w_yaml[str(k).strip()] = float(v)
            except Exception:
                pass
        if w_yaml:
            cfg.weights.update(_normalize_weights(w_yaml))

    # portfolio
    pf = raw.get("portfolio", [])
    if isinstance(pf, list):
        out = []
        for row in pf:
            if isinstance(row, dict) and row.get("ticker"):
                r = dict(row)
                r["ticker"] = str(r["ticker"]).strip().upper()
                out.append(r)
        cfg.portfolio = out

    cfg.watchlist = [s.strip().upper() for s in _as_list_str(raw.get("watchlist", cfg.watchlist))]
    cfg.new_candidates = [s.strip().upper() for s in _as_list_str(raw.get("new_candidates", []))]

    # ticker_map
    tm = raw.get("ticker_map", {})
    if isinstance(tm, dict):
        cfg.ticker_map = {str(k).strip().upper(): str(v).strip() for k, v in tm.items()}

    # ✅ learned weights override (pokud existují)
    learned = _load_learned_weights(cfg.state_dir)
    if learned:
        cfg.weights.update(learned)
        cfg.weights = _normalize_weights(cfg.weights)

    return cfg