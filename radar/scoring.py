# radar/scoring.py
from __future__ import annotations
from typing import Dict


def clamp(x: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, x))


def score_pe(pe: float | None) -> float:
    if pe is None:
        return 5.0

    if pe < 10:
        return 9.0     # levné
    if pe < 20:
        return 8.0
    if pe < 35:
        return 6.0
    if pe < 60:
        return 4.0
    return 2.0         # drahé


def score_growth(growth: float | None) -> float:
    if growth is None:
        return 5.0

    if growth > 30:
        return 10.0
    if growth > 15:
        return 8.0
    if growth > 5:
        return 6.0
    if growth > 0:
        return 5.0
    return 2.0         # klesající tržby


def score_margin(margin: float | None) -> float:
    if margin is None:
        return 5.0

    if margin > 30:
        return 10.0
    if margin > 15:
        return 8.0
    if margin > 5:
        return 6.0
    return 3.0


def score_debt(debt_equity: float | None) -> float:
    if debt_equity is None:
        return 5.0

    if debt_equity < 0.3:
        return 9.0
    if debt_equity < 0.7:
        return 7.0
    if debt_equity < 1.5:
        return 5.0
    return 2.0


def compute_score(features: Dict, weights: Dict | None = None) -> float:
    weights = weights or {}

    w_mom = float(weights.get("momentum", 0.25))
    w_cat = float(weights.get("catalyst", 0.20))
    w_reg = float(weights.get("market_regime", 0.20))
    w_fund = float(weights.get("fundamentals", 0.35))

    momentum = float(features.get("momentum_score", 5.0))
    catalyst = float(features.get("catalyst_score", 5.0))
    regime = float(features.get("regime_score", 5.0))

    pe = score_pe(features.get("pe"))
    growth = score_growth(features.get("growth"))
    margin = score_margin(features.get("margin"))
    debt = score_debt(features.get("debt_equity"))

    fundamentals = (pe + growth + margin + debt) / 4.0

    total = (
        momentum * w_mom +
        catalyst * w_cat +
        regime * w_reg +
        fundamentals * w_fund
    )

    return clamp(total)