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
    os.makedirs(cfg.state_dir, exist_ok=True)
    return os.path.join(cfg.state_dir, "learned_weights.json")


def _load(cfg: RadarConfig) -> Dict[str, float]:
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


def _save(cfg: RadarConfig, w: Dict[str, float]) -> None:
    path = _weights_path(cfg)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(w, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _normalize(w: Dict[str, float]) -> Dict[str, float]:
    s = sum(float(v) for v in w.values() if v is not None)
    if s <= 0:
        return w
    return {k: float(v) / s for k, v in w.items()}


def learn_weekly_weights(cfg: RadarConfig, now: Optional[datetime] = None, st: Optional[State] = None) -> Dict[str, Any]:
    now = now or datetime.now()
    st = st or State(cfg.state_dir)

    uni, _ = resolved_universe(cfg, universe=None)

    base = dict(getattr(cfg, "weights", {}) or {})
    if not base:
        base = {"momentum": 0.25, "volume": 0.20, "volatility": 0.15, "catalyst": 0.20, "market_regime": 0.20}

    learned = _load(cfg) or base
    after = dict(learned)

    # konzervativní tweak (stabilní)
    if len(uni) >= 20:
        after["market_regime"] = float(after.get("market_regime", 0.2)) + 0.01
        after["momentum"] = max(0.01, float(after.get("momentum", 0.2)) - 0.01)

    after = _normalize(after)
    _save(cfg, after)

    st.save()
    return {
        "ok": True,
        "method": "weekly_conservative",
        "resolved_n": len(uni),
        "before": learned,
        "after": after,
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
    }