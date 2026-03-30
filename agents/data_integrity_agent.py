
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from symbol_utils import filter_enabled_symbols, load_ticker_map, provider_symbol, looks_valid_symbol

REPORT_PATH = Path("data/data_integrity_report.json")


def _norm(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _infer_provider_ok(symbol: str) -> bool:
    internal = _norm(symbol)
    if not internal:
        return False
    if not looks_valid_symbol(internal):
        return False
    mapped = provider_symbol(internal, 'fmp')
    return bool(mapped) and mapped == mapped.strip().upper()


def validate_symbols(symbols: list[str]) -> dict[str, Any]:
    filtered = filter_enabled_symbols(symbols)
    ticker_map = load_ticker_map()
    seen: set[str] = set()
    valid: list[str] = []
    disabled: list[str] = []
    suspicious: list[dict[str, Any]] = []
    for raw in symbols:
        symbol = _norm(raw)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        row = ticker_map.get(symbol, {}) if isinstance(ticker_map, dict) else {}
        if row and not bool(row.get('enabled', True)):
            disabled.append(symbol)
            continue
        provider_ok = _infer_provider_ok(symbol)
        if not provider_ok:
            suspicious.append({'symbol': symbol, 'reason': 'missing_provider_mapping'})
            continue
        valid.append(symbol)
    result = {
        'input_count': len([s for s in symbols if _norm(s)]),
        'valid_symbols': valid,
        'disabled_symbols': disabled,
        'suspicious_symbols': suspicious,
        'valid_count': len(valid),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def score_row_quality(row: dict[str, Any]) -> dict[str, Any]:
    quality = 1.0
    reasons: list[str] = []
    symbol = _norm(row.get('symbol'))
    if not symbol:
        return {'data_quality_score': 0.0, 'data_quality_label': 'bad', 'data_quality_reasons': ['missing_symbol']}
    price = row.get('price')
    try:
        price_f = float(price)
    except Exception:
        price_f = 0.0
    if price_f <= 0:
        quality -= 0.45
        reasons.append('missing_or_zero_price')
    source = str(row.get('source', '') or '').strip().lower()
    if 'fallback' in source or 'scaffold' in source:
        quality -= 0.35
        reasons.append('fallback_source')
    if abs(float(row.get('change_pct', 0.0) or 0.0)) > 25:
        quality -= 0.2
        reasons.append('extreme_move_needs_validation')
    if abs(float(row.get('atr_proxy_pct', 0.0) or 0.0)) > 12:
        quality -= 0.1
        reasons.append('high_volatility_proxy')
    if not _infer_provider_ok(symbol):
        quality -= 0.35
        reasons.append('provider_mapping_unclear')
    if '_' in symbol:
        quality -= 0.25
        reasons.append('synthetic_or_underscored_symbol')
    score = round(max(0.0, min(1.0, quality)), 2)
    if score >= 0.8:
        label = 'good'
    elif score >= 0.6:
        label = 'ok'
    elif score >= 0.4:
        label = 'weak'
    else:
        label = 'bad'
    return {'data_quality_score': score, 'data_quality_label': label, 'data_quality_reasons': reasons}


def build_data_health_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assessed = []
    counts = {'good': 0, 'ok': 0, 'weak': 0, 'bad': 0}
    for row in rows:
        info = score_row_quality(row)
        label = str(info['data_quality_label'])
        counts[label] = counts.get(label, 0) + 1
        assessed.append({**row, **info})
    avg = round(sum(float(r['data_quality_score']) for r in assessed) / len(assessed), 2) if assessed else 0.0
    return {'avg_quality': avg, 'counts': counts, 'rows': assessed}
