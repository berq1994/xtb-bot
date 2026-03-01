# radar/learn.py
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from radar.config import RadarConfig
from radar.state import State
from radar.universe import resolved_universe


def _weights_path(cfg: RadarConfig) -> str:
    state_dir = getattr(cfg, "state_dir", ".state")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, "learned_weights.json")


def _load_learned(cfg: RadarConfig) -> Dict[str, float]:
    path = _weights_path(cfg)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        out: Dict[str, float] = {}
        if isinstance(data, dict):
            for k, v in data.items():
                try:
                    out[str(k)] = float(v)
                except Exception:
                    continue
        return out
    except Exception:
        return {}


def _save_learned(cfg: RadarConfig, weights: Dict[str, float]) -> None:
    path = _weights_path(cfg)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(weights, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _normalize(w: Dict[str, float]) -> Dict[str, float]:
    s = 0.0
    for v in w.values():
        try:
            s += float(v)
        except Exception:
            pass
    if s <= 0:
        return w
    return {k: float(v) / s for k, v in w.items()}


def learn_weekly_weights(cfg: RadarConfig, now: Optional[datetime] = None, st: Optional[State] = None) -> Dict[str, Any]:
    """
    Lightweight weekly learning:
    - načte univerzum (kvůli kompatibilitě; i když algoritmus může být placeholder)
    - načte cfg.weights a learned_weights.json
    - provede malou úpravu vah (placeholder/konzervativní)
    - uloží learned_weights.json
    """
    now = now or datetime.now()
    st = st or State(getattr(cfg, "state_dir", ".state"))

    # --- fix: resolved_universe supports universe kwarg now ---
    resolved, mapping = resolved_universe(cfg, universe=None)

    base_weights = getattr(cfg, "weights", None) or {}
    base: Dict[str, float] = {}
    if isinstance(base_weights, dict) and base_weights:
        for k, v in base_weights.items():
            try:
                base[str(k)] = float(v)
            except Exception:
                continue
    if not base:
        # safe default
        base = {"momentum": 0.25, "volume": 0.20, "volatility": 0.15, "catalyst": 0.20, "market_regime": 0.20}

    learned_before = _load_learned(cfg)
    before = learned_before or base

    # --- Konzervativní "learning" (aby to bylo stabilní a nikdy se to nerozjelo) ---
    # Jestli chceš později smart learning podle výsledků (return, winrate), doplníme.
    after = dict(before)

    # mikrotweak: pokud je universe velké, trochu zvedni market_regime a zlehka sniž momentum
    n = len(resolved)
    if n >= 20:
        after["market_regime"] = float(after.get("market_regime", 0.2)) + 0.01
        after["momentum"] = max(0.01, float(after.get("momentum", 0.2)) - 0.01)

    after = _normalize(after)
    _save_learned(cfg, after)

    return {
        "ok": True,
        "method": "weekly_conservative",
        "notes": f"universe={len(resolved)} tickers",
        "resolved_n": len(resolved),
        "before": before,
        "after": after,
        "mapping_n": len(mapping),
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
    }