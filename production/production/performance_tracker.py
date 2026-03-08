import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

REG_FILE = Path('.state/history/alert_registry.jsonl')
SUMMARY_FILE = Path('.state/history/alert_performance_summary.json')


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _hit_from_row(row: Dict[str, Any]) -> float | None:
    directional = row.get('directional_hit')
    if directional is not None:
        try:
            return 1.0 if bool(directional) else 0.0
        except Exception:
            pass

    for key in ('outcome_15m', 'outcome_60m', 'outcome_1d'):
        value = _safe_float(row.get(key))
        if value is not None:
            return 1.0 if value > 0 else 0.0
    return None


def summarize_performance(rows: Iterable[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    records = list(rows) if rows is not None else _read_jsonl(REG_FILE)

    buckets: Dict[str, Dict[str, int]] = defaultdict(lambda: {'total': 0, 'hits': 0, 'misses': 0})
    scored_records = 0
    overall_hits = 0

    for row in records:
        hit = _hit_from_row(row)
        category = str(row.get('category', 'unknown')).upper()
        status = str(row.get('status', 'unknown')).upper()
        priority = str(row.get('priority', 'unknown')).upper()

        if hit is None:
            continue

        scored_records += 1
        overall_hits += int(hit)

        for prefix, key in (('category', category), ('status', status), ('priority', priority)):
            bucket = buckets[f'{prefix}:{key}']
            bucket['total'] += 1
            if hit >= 1.0:
                bucket['hits'] += 1
            else:
                bucket['misses'] += 1

    by_category: Dict[str, Any] = {}
    by_status: Dict[str, Any] = {}
    by_priority: Dict[str, Any] = {}
    for bucket_key, data in buckets.items():
        prefix, key = bucket_key.split(':', 1)
        payload = {
            'total': data['total'],
            'hits': data['hits'],
            'misses': data['misses'],
            'hit_rate': round(data['hits'] / max(1, data['total']), 3),
        }
        if prefix == 'category':
            by_category[key] = payload
        elif prefix == 'status':
            by_status[key] = payload
        elif prefix == 'priority':
            by_priority[key] = payload

    summary = {
        'records': len(records),
        'scored_records': scored_records,
        'pending_records': len(records) - scored_records,
        'overall_hit_rate': round(overall_hits / max(1, scored_records), 3) if scored_records else 0.0,
        'by_category': by_category,
        'by_status': by_status,
        'by_priority': by_priority,
    }
    _write_json(SUMMARY_FILE, summary)
    return summary
