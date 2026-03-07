# radar/learn.py
from __future__ import annotations

import os
import json
import math
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional

import yfinance as yf

from radar.universe import resolved_universe
from radar.config import RadarConfig


def _clamp(x: float, lo: float = 0.05, hi: float = 0.60) -> float:
    return max(lo, min(hi, x))


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    s = sum(float(v) for v in weights.values() if isinstance(v, (int, float)))
    if s <= 0:
        return weights
    return {k: float(v) / s for k, v in weights.items()}


def _safe_float(x) -> Optional[float]:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _history(ticker: str, period: str = "9mo") -> Optional[Any]:
    try:
        h = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
        if h is None or h.empty:
            return None
        return h
    except Exception:
        return None


def _ret_1d(close_series) -> Optional[float]:
    try:
        c = close_series.dropna()
        if len(c) < 2:
            return None
        return (float(c.iloc[-1]) - float(c.iloc[-2])) / float(c.iloc[-2]) * 100.0
    except Exception:
        return None


def _ret_5d(close_series) -> Optional[float]:
    try:
        c = close_series.dropna()
        if len(c) < 6:
            return None
        return (float(c.iloc[-1]) - float(c.iloc[-6])) / float(c.iloc[-6]) * 100.0
    except Exception:
        return None


def _vol_ratio(volume_series) -> Optional[float]:
    try:
        v = volume_series.dropna()
        if len(v) < 25:
            return None
        avg20 = float(v.tail(20).mean())
        lastv = float(v.iloc[-1])
        if avg20 <= 0:
            return None
        return lastv / avg20
    except Exception:
        return None


def _corr(xs: List[float], ys: List[float]) -> float:
    # Pearson corr (bez numpy)
    n = min(len(xs), len(ys))
    if n < 12:
        return 0.0
    x = xs[-n:]
    y = ys[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 0 or vy <= 0:
        return 0.0
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return cov / math.sqrt(vx * vy)


def learn_weekly_weights(cfg: RadarConfig, now: datetime, st=None) -> Dict[str, Any]:
    """
    (1) Learn weights:
    - vezmeme portfolio+watchlist+new_candidates (+ benchmark SPY)
    - spočítáme korelace jednoduchých feature proxy vs budoucí 5D return:
        * momentum proxy: 1D return magnitude (abs)
        * rel_strength proxy: (ticker 5D - SPY 5D)
        * volatility_volume proxy: volume ratio
      catalyst a market_regime zatím necháme stabilní (nemáme historické zprávy v cache)
    - upravíme váhy jemně (ne agresivně), normalizujeme a uložíme do:
        {state_dir}/learned_weights.json
    """
    before = dict(cfg.weights or {})
    # fallback pro chybějící klíče
    for k, v in {
        "momentum": 0.25,
        "rel_strength": 0.20,
        "volatility_volume": 0.15,
        "catalyst": 0.20,
        "market_regime": 0.20,
    }.items():
        before.setdefault(k, float(v))

    # Universe
    resolved, _ = resolved_universe(cfg, universe=None)

    # Pro RS potřebujeme SPY
    bench = (cfg.benchmarks or {}).get("spy", "SPY")
    spy_h = _history(bench, period="9mo")
    spy_close = spy_h["Close"] if spy_h is not None and "Close" in spy_h else None

    mom_x, rs_x, vol_x, y_fwd = [], [], [], []
    used = 0
    fail = 0

    # Bereme max 40 tickerů (aby learn nebyl těžký)
    for t in resolved[:40]:
        h = _history(t, period="9mo")
        if h is None or "Close" not in h:
            fail += 1
            continue

        close = h["Close"]
        vol = h["Volume"] if "Volume" in h else None

        r1 = _ret_1d(close)          # proxy momentum
        r5 = _ret_5d(close)          # proxy future move
        vr = _vol_ratio(vol) if vol is not None else None

        if r1 is None or r5 is None:
            fail += 1
            continue

        # RS = ticker5d - spy5d
        rs = None
        if spy_close is not None:
            spy5 = _ret_5d(spy_close)
            if spy5 is not None:
                rs = r5 - spy5

        mom_x.append(abs(r1))
        rs_x.append(rs if rs is not None else 0.0)
        vol_x.append(vr if vr is not None else 1.0)
        y_fwd.append(r5)
        used += 1

    # Pokud není dost dat, nic neměň
    if used < 12:
        after = _normalize(before)
        _save_learned(cfg, after)
        return {
            "before": _normalize(before),
            "after": after,
            "method": "fallback(no_data)",
            "notes": f"Nedostatek dat pro learn (used={used}, fail={fail}). Nechávám původní váhy.",
        }

    # Korelace -> “síla signálu”
    c_mom = abs(_corr(mom_x, y_fwd))
    c_rs = abs(_corr(rs_x, y_fwd))
    c_vol = abs(_corr(vol_x, y_fwd))

    # Jemná adaptace: posuneme váhy jen o malý delta podle síly signálu
    # Catalyst + regime necháme stabilní, protože je nemáme historicky robustně
    base = _normalize(before)
    after = dict(base)

    # scale 0..1
    sig_sum = (c_mom + c_rs + c_vol)
    if sig_sum <= 0:
        sig_mom = sig_rs = sig_vol = 1 / 3
    else:
        sig_mom = c_mom / sig_sum
        sig_rs = c_rs / sig_sum
        sig_vol = c_vol / sig_sum

    # kolik procent z “trainable pool” přerozdělíme (max 12% aby to nebylo divoké)
    train_pool = base["momentum"] + base["rel_strength"] + base["volatility_volume"]
    shift = min(0.12, 0.25 * train_pool)

    # nové cíle v rámci pool
    target_mom = train_pool * (0.20 + 0.80 * sig_mom)
    target_rs = train_pool * (0.20 + 0.80 * sig_rs)
    target_vol = train_pool * (0.20 + 0.80 * sig_vol)

    # Interpolace base -> target
    # “shift” určuje, jak moc se přiblížíme k targetům
    def blend(base_v: float, target_v: float) -> float:
        return (1 - shift) * base_v + shift * target_v

    after["momentum"] = blend(base["momentum"], target_mom)
    after["rel_strength"] = blend(base["rel_strength"], target_rs)
    after["volatility_volume"] = blend(base["volatility_volume"], target_vol)

    # catalyst/regime ponecháme, ale ohlídáme minima
    after["catalyst"] = _clamp(after.get("catalyst", base["catalyst"]), 0.10, 0.40)
    after["market_regime"] = _clamp(after.get("market_regime", base["market_regime"]), 0.10, 0.40)

    after = _normalize(after)
    _save_learned(cfg, after)

    return {
        "before": base,
        "after": after,
        "method": "corr(price/volume)->soft_reweight",
        "notes": f"used={used}, fail={fail}, corr(|1D|,5D)={c_mom:.2f}, corr(RS,5D)={c_rs:.2f}, corr(VR,5D)={c_vol:.2f}",
    }


def _save_learned(cfg: RadarConfig, weights: Dict[str, float]) -> None:
    state_dir = getattr(cfg, "state_dir", ".state") or ".state"
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "learned_weights.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(weights, f, ensure_ascii=False, indent=2)