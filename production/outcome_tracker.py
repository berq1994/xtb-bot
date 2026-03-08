import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

REG_DIR = Path('.state/history')
REG_FILE = REG_DIR / 'alert_registry.jsonl'
SUMMARY_FILE = REG_DIR / 'alert_registry_summary.json'


def register_alerts(alerts: List[Dict]) -> Dict:
    REG_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    entries = []
    for item in alerts:
        entries.append({
            'ts_utc': now,
            'category': item.get('category'),
            'title': item.get('title'),
            'tickers': item.get('tickers', []),
            'priority': item.get('priority'),
            'status': item.get('status'),
            'timeframe': item.get('timeframe'),
            'bias': item.get('bias'),
            'outcome_15m': None,
            'outcome_60m': None,
            'outcome_1d': None,
        })
    with REG_FILE.open('a', encoding='utf-8') as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + '
')

    all_entries = []
    if REG_FILE.exists():
        with REG_FILE.open('r', encoding='utf-8') as fh:
            all_entries = [json.loads(line) for line in fh if line.strip()]
    summary = {
        'records': len(all_entries),
        'latest_batch': len(entries),
        'latest_ts_utc': now,
    }
    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary
