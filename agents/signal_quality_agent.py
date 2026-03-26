from __future__ import annotations

import os
from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _grade_bonus(grade: str) -> float:
    mapping = {
        'A': 1.1,
        'B': 0.8,
        'C': 0.45,
        'D': 0.0,
    }
    return mapping.get(str(grade or 'D').strip().upper(), 0.0)


def _category_bonus(category: str, held: bool) -> float:
    category = str(category or '').strip()
    if category == 'portfolio_defense':
        return 1.4 if held else 0.5
    if category == 'drawdown_control':
        return 1.15 if held else 0.2
    if category == 'winner_management':
        return 0.95 if held else 0.1
    if category == 'earnings_watch':
        return 0.8
    if category == 'breakout_watch':
        return 0.7
    if category == 'risk_watch':
        return 0.55
    if category == 'pullback_control':
        return 0.6 if held else 0.2
    return 0.15


def _regime_bonus(regime: str, trend: str, category: str) -> float:
    regime = str(regime or '').strip()
    trend = str(trend or '').strip()
    category = str(category or '').strip()
    if regime == 'risk_off' and category in {'portfolio_defense', 'drawdown_control', 'risk_watch'}:
        return 0.45
    if regime == 'risk_on' and category in {'breakout_watch', 'winner_management', 'earnings_watch'}:
        return 0.35
    if regime == 'risk_off' and trend == 'up':
        return -0.1
    return 0.0


def action_hint(item: dict[str, Any]) -> str:
    category = str(item.get('category', '')).strip()
    if category == 'portfolio_defense':
        return 'prověřit negativní zprávy a úroveň, kde bys už nechtěl nést další riziko'
    if category == 'drawdown_control':
        return 'zkontrolovat, zda nejde o změnu teze, ne jen běžný výkyv'
    if category == 'winner_management':
        return 'hlídat výběr části zisku nebo přitažení stopu, ne vstup za každou cenu'
    if category == 'earnings_watch':
        return 'sledovat potvrzení po výsledcích a nevstupovat bez pokračování'
    if category == 'breakout_watch':
        return 'čekat na potvrzení síly a zdrojů, nehonit slabý breakout'
    if category == 'pullback_control':
        return 'ověřit, zda jde o zdravý pullback a ne počátek většího oslabení'
    return 'zkontrolovat graf, zprávy a relevance k portfoliu'


def score_actionability(item: dict[str, Any], regime: str = 'mixed') -> dict[str, Any]:
    held = bool(item.get('held'))
    change_pct = abs(float(item.get('change_pct', 0.0) or 0.0))
    momentum_5d = abs(float(item.get('momentum_5d', 0.0) or 0.0))
    sentiment = str(item.get('sentiment_label') or item.get('sentiment') or 'neutral').strip().lower()
    evidence_score = float(item.get('evidence_score', 0.0) or 0.0)
    evidence_grade = str(item.get('evidence_grade', 'D') or 'D').strip().upper()
    category = str(item.get('category', 'watchlist_monitor') or 'watchlist_monitor').strip()
    trend = str(item.get('trend', 'flat') or 'flat').strip()
    source_count = int(item.get('source_count', 0) or 0)
    atr_proxy_pct = float(item.get('atr_proxy_pct', 0.0) or 0.0)
    pnl = item.get('pnl_vs_cost_pct')
    pnl_value = float(pnl or 0.0) if pnl not in (None, '') else None

    score = 0.0
    score += 1.2 if held else 0.15
    score += _clamp(change_pct / 2.1, 0.0, 1.8)
    score += _clamp(momentum_5d / 4.0, 0.0, 1.1)
    score += evidence_score * 1.45
    score += _grade_bonus(evidence_grade)
    score += _category_bonus(category, held)
    score += _regime_bonus(regime, trend, category)

    if source_count >= 3:
        score += 0.65
    elif source_count == 2:
        score += 0.35
    elif source_count == 1:
        score += 0.1
    else:
        score -= 0.35

    if sentiment == 'positive' and trend == 'up':
        score += 0.35
    elif sentiment == 'negative' and category in {'portfolio_defense', 'drawdown_control', 'risk_watch'}:
        score += 0.45
    elif sentiment == 'negative' and not held:
        score -= 0.25

    if atr_proxy_pct >= 4.0:
        score -= 0.25

    if pnl_value is not None:
        if pnl_value >= 18 and category == 'winner_management':
            score += 0.5
        if pnl_value <= -8 and category in {'portfolio_defense', 'drawdown_control'}:
            score += 0.5

    suppress_reason = ''
    suppressed = False
    if not held and evidence_grade == 'D' and source_count <= 1:
        suppressed = True
        suppress_reason = 'slabé potvrzení mimo portfolio'
    elif not held and score < 3.2:
        suppressed = True
        suppress_reason = 'nízká akčnost mimo portfolio'
    elif held and score < 2.8 and change_pct < 2.0:
        suppressed = True
        suppress_reason = 'slabý pohyb bez nutnosti zásahu'

    if score >= 5.0 or (held and category in {'portfolio_defense', 'drawdown_control'} and change_pct >= 3.0):
        bucket = 'urgent'
    elif score >= 4.1:
        bucket = 'high'
    elif score >= 3.2:
        bucket = 'medium'
    else:
        bucket = 'low'

    return {
        'actionability_score': round(score, 2),
        'action_bucket': bucket,
        'action_hint': action_hint(item),
        'suppressed': suppressed,
        'suppress_reason': suppress_reason,
    }


def build_action_queue(items: list[dict[str, Any]], regime: str = 'mixed', limit: int | None = None) -> list[dict[str, Any]]:
    min_score = float(os.getenv('ACTION_QUEUE_MIN_SCORE', '3.2') or 3.2)
    limit_value = int(os.getenv('ACTION_QUEUE_LIMIT', str(limit or 5)) or (limit or 5))
    enriched: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        item.update(score_actionability(item, regime))
        if item.get('suppressed'):
            enriched.append(item)
            continue
        if float(item.get('actionability_score', 0.0) or 0.0) < min_score:
            item['suppressed'] = True
            item['suppress_reason'] = 'pod prahem akční fronty'
            enriched.append(item)
            continue
        enriched.append(item)
    queue = [row for row in enriched if not row.get('suppressed')]
    queue.sort(key=lambda x: (float(x.get('actionability_score', 0.0) or 0.0), float(x.get('priority_score', 0.0) or 0.0)), reverse=True)
    return queue[:limit_value]
