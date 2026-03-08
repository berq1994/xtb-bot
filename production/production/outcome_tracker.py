import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

REG_DIR = Path('.state/history')
REG_FILE = REG_DIR / 'alert_registry.jsonl'
SUMMARY_FILE = REG_DIR / 'alert_registry_summary.json'


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + '\n')


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
    _ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def register_alerts(alerts: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    REG_DIR.mkdir(parents=True, exist_ok=True)
    now = _utc_now_iso()
    latest_entries: List[Dict[str, Any]] = []

    for item in alerts:
        entry = {
            'ts_utc': now,
            'category': item.get('category'),
            'title': item.get('title'),
            'tickers': item.get('tickers', []),
            'priority': item.get('priority'),
            'status': item.get('status'),
            'timeframe': item.get('timeframe'),
            'bias': item.get('bias'),
            'confidence': item.get('confidence'),
            'impact': item.get('impact'),
            'outcome_15m': item.get('outcome_15m'),
            'outcome_60m': item.get('outcome_60m'),
            'outcome_1d': item.get('outcome_1d'),
            'directional_hit': item.get('directional_hit'),
            'scored': item.get('directional_hit') is not None,
        }
        latest_entries.append(entry)
        _append_jsonl(REG_FILE, entry)

    all_entries = _read_jsonl(REG_FILE)
    pending_records = sum(1 for row in all_entries if not row.get('scored'))
    scored_records = len(all_entries) - pending_records

    category_counts = Counter(str(row.get('category', 'unknown')).upper() for row in all_entries)
    status_counts = Counter(str(row.get('status', 'unknown')).upper() for row in all_entries)

    summary = {
        'records': len(all_entries),
        'latest_batch': len(latest_entries),
        'latest_ts_utc': now,
        'pending_records': pending_records,
        'scored_records': scored_records,
        'category_counts': dict(category_counts),
        'status_counts': dict(status_counts),
    }
    _write_json(SUMMARY_FILE, summary)
    return summary
