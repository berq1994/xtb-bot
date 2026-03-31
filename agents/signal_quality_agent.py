from __future__ import annotations

import os
from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _grade_bonus(grade: str) -> float:
    mapping = {'A': 1.25, 'B': 0.9, 'C': 0.45, 'D': -0.15}
    return mapping.get(str(grade or 'D').strip().upper(), -0.15)


def _category_bonus(category: str, held: bool) -> float:
    category = str(category or '').strip()
    if category == 'portfolio_defense':
        return 1.55 if held else 0.35
    if category == 'drawdown_control':
        return 1.25 if held else 0.2
    if category == 'winner_management':
        return 1.0 if held else 0.15
    if category == 'earnings_watch':
        return 0.8
    if category == 'breakout_watch':
        return 0.65
    if category == 'risk_watch':
        return 0.6
    if category == 'pullback_control':
        return 0.75 if held else 0.2
    return 0.1


def _regime_bonus(regime: str, trend: str, category: str) -> float:
    regime = str(regime or '').strip()
    trend = str(trend or '').strip()
    category = str(category or '').strip()
    if regime == 'risk_off' and category in {'portfolio_defense', 'drawdown_control', 'risk_watch'}:
        return 0.55
    if regime == 'risk_on' and category in {'breakout_watch', 'winner_management', 'earnings_watch'}:
        return 0.35
    if regime == 'risk_off' and trend == 'up':
        return -0.15
    return 0.0


def action_hint(item: dict[str, Any]) -> str:
    buy_decision = str(item.get('buy_decision') or '').strip()
    buy_trigger = str(item.get('buy_trigger') or '').strip()
    if buy_decision == 'buy_breakout':
        return f'vstup až po potvrzeném breakoutu; trigger: {buy_trigger}'
    if buy_decision == 'buy_pullback':
        return f'hledat zdravý pullback v trendu; trigger: {buy_trigger}'
    if buy_decision == 'buy_reversal':
        return f'agresivnější obratová varianta; trigger: {buy_trigger}'
    if buy_decision == 'trim_watch':
        return f'zvážit výběr části zisku nebo přitažení stopu; trigger: {buy_trigger}'
    if buy_decision == 'avoid':
        return f'nekupovat bez nového potvrzení; trigger: {buy_trigger}'

    category = str(item.get('category', '')).strip()
    if category == 'portfolio_defense':
        return 'prověřit negativní zprávy, support a hranici, kde už nechceš nést další riziko'
    if category == 'drawdown_control':
        return 'zkontrolovat, zda nejde o změnu teze, ne jen běžný výkyv'
    if category == 'winner_management':
        return 'hlídat částečný výběr zisku nebo přitažení stopu, ne honit další vstup'
    if category == 'earnings_watch':
        return 'sledovat potvrzení po výsledcích a nevstupovat bez pokračování'
    if category == 'breakout_watch':
        return 'čekat na potvrzení síly a zdrojů, nehonit slabý breakout'
    if category == 'pullback_control':
        return 'ověřit, zda jde o zdravý pullback a ne počátek většího oslabení'
    return 'zkontrolovat graf, zprávy a relevance k portfoliu'


def _urgency_label(bucket: str) -> str:
    return {
        'urgent': 'ihned zkontrolovat',
        'high': 'dnes sledovat',
        'medium': 'mít na očích',
        'low': 'jen informačně',
    }.get(bucket, 'jen informačně')


def score_actionability(item: dict[str, Any], regime: str = 'mixed') -> dict[str, Any]:
    held = bool(item.get('held'))
    change_pct = abs(float(item.get('change_pct', 0.0) or 0.0))
    momentum_5d = abs(float(item.get('momentum_5d', 0.0) or 0.0))
    momentum_20d = abs(float(item.get('momentum_20d', 0.0) or 0.0))
    sentiment = str(item.get('sentiment_label') or item.get('sentiment') or 'neutral').strip().lower()
    evidence_score = float(item.get('evidence_score', 0.0) or 0.0)
    evidence_grade = str(item.get('evidence_grade', 'D') or 'D').strip().upper()
    category = str(item.get('category', 'watchlist_monitor') or 'watchlist_monitor').strip()
    trend = str(item.get('trend', 'flat') or 'flat').strip()
    source_count = int(item.get('source_count', 0) or 0)
    source_name = str(item.get('news_source') or item.get('source') or '').strip().lower()
    atr_proxy_pct = float(item.get('atr_proxy_pct', 0.0) or 0.0)
    pnl = item.get('pnl_vs_cost_pct')
    pnl_value = float(pnl or 0.0) if pnl not in (None, '') else None
    data_quality_score = float(item.get('data_quality_score', 0.7) or 0.7)
    thesis_strength = float(item.get('thesis_strength', 0.45) or 0.45)
    ta_score = float(item.get('ta_score', 0.0) or 0.0)
    official_count = int(item.get('official_item_count', 0) or 0)
    buy_decision = str(item.get('buy_decision') or 'watch').strip()
    setup_type = str(item.get('technical_setup') or '').strip()

    score = 0.0
    score += 1.35 if held else 0.1
    score += _clamp(change_pct / 2.1, 0.0, 1.9)
    score += _clamp(momentum_5d / 4.0, 0.0, 1.0)
    score += _clamp(momentum_20d / 8.0, 0.0, 0.8)
    score += evidence_score * 1.55
    score += _grade_bonus(evidence_grade)
    score += _category_bonus(category, held)
    score += _regime_bonus(regime, trend, category)
    score += max(0.0, data_quality_score - 0.55) * 1.4
    score += max(0.0, thesis_strength - 0.45) * 1.0
    score += max(0.0, ta_score - 4.5) * 0.45
    score += min(0.9, official_count * 0.28)

    if buy_decision in {'buy_breakout', 'buy_pullback'}:
        score += 0.75
    elif buy_decision == 'buy_reversal':
        score += 0.35
    elif buy_decision == 'trim_watch' and held:
        score += 0.45
    elif buy_decision == 'avoid' and not held:
        score -= 0.45

    if setup_type == 'breakout':
        score += 0.25
    elif setup_type == 'breakdown':
        score += 0.15 if held else -0.25

    if source_count >= 3:
        score += 0.7
    elif source_count == 2:
        score += 0.35
    elif source_count == 1:
        score += 0.05
    else:
        score -= 0.55

    if sentiment == 'positive' and trend == 'up':
        score += 0.35
    elif sentiment == 'negative' and category in {'portfolio_defense', 'drawdown_control', 'risk_watch'}:
        score += 0.5
    elif sentiment == 'negative' and not held:
        score -= 0.3

    if atr_proxy_pct >= 4.0:
        score -= 0.25
    if data_quality_score < 0.5:
        score -= 0.55

    if pnl_value is not None:
        if pnl_value >= 18 and category == 'winner_management':
            score += 0.6
        if pnl_value <= -8 and category in {'portfolio_defense', 'drawdown_control'}:
            score += 0.55

    suppressed = False
    suppress_reason = ''
    if data_quality_score < 0.55:
        suppressed = True
        suppress_reason = 'slabá datová kvalita'
    elif 'scaffold' in source_name and evidence_grade in {'D', '?'}:
        suppressed = True
        suppress_reason = 'scaffold bez důkazů'
    elif not held and evidence_grade == 'D' and source_count <= 1:
        suppressed = True
        suppress_reason = 'slabé potvrzení mimo portfolio'
    elif not held and buy_decision == 'avoid' and ta_score < 5.0:
        suppressed = True
        suppress_reason = 'technicky nepříznivé bez držení v portfoliu'
    elif not held and thesis_strength < 0.4 and score < 3.8:
        suppressed = True
        suppress_reason = 'bez teze a nízká akčnost mimo portfolio'
    elif not held and str(item.get('fundamental_provider','')).lower().find('fallback') != -1 and evidence_grade in {'D', '?'} and official_count == 0:
        suppressed = True
        suppress_reason = 'slabé fundamenty i důkazy mimo portfolio'
    elif not held and score < 3.4:
        suppressed = True
        suppress_reason = 'nízká akčnost mimo portfolio'
    elif held and score < 3.0 and change_pct < 2.0:
        suppressed = True
        suppress_reason = 'slabý pohyb bez nutnosti zásahu'

    if score >= 5.4 or (held and category in {'portfolio_defense', 'drawdown_control'} and change_pct >= 3.0):
        bucket = 'urgent'
    elif score >= 4.4:
        bucket = 'high'
    elif score >= 3.4:
        bucket = 'medium'
    else:
        bucket = 'low'

    if evidence_grade in {'D', '?'} or 'scaffold' in source_name:
        if bucket == 'urgent':
            bucket = 'high' if held else 'low'
        elif bucket == 'high' and not held:
            bucket = 'medium'

    delivery_channel = 'telegram' if held and bucket in {'urgent', 'high'} else ('email' if bucket in {'high', 'medium'} else 'none')

    return {
        'actionability_score': round(score, 2),
        'action_bucket': bucket,
        'urgency_label': _urgency_label(bucket),
        'delivery_channel': delivery_channel,
        'action_hint': action_hint(item),
        'suppressed': suppressed,
        'suppress_reason': suppress_reason,
    }


def build_action_queue(items: list[dict[str, Any]], regime: str = 'mixed', limit: int | None = None) -> list[dict[str, Any]]:
    min_score = float(os.getenv('ACTION_QUEUE_MIN_SCORE', '3.4') or 3.4)
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
    queue.sort(key=lambda x: (
        1 if bool(x.get('held')) else 0,
        float(x.get('actionability_score', 0.0) or 0.0),
        float(x.get('priority_score', 0.0) or 0.0),
        float(x.get('data_quality_score', 0.0) or 0.0),
        float(x.get('ta_score', 0.0) or 0.0),
    ), reverse=True)
    return queue[:limit_value]
