import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

HISTORY_DIR = Path('.state/history')
HISTORY_FILE = HISTORY_DIR / 'block14_history.jsonl'
METRICS_FILE = HISTORY_DIR / 'block14_metrics.json'


def archive_run(payload: Dict, alerts: List[Dict], briefing_items: List[Dict], evaluation: Dict) -> Dict:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        'ts_utc': datetime.now(timezone.utc).isoformat(),
        'governance_mode': payload.get('report', {}).get('governance_mode'),
        'alert_count': len(alerts),
        'approved_count': evaluation.get('approved_count', 0),
        'rejected_count': evaluation.get('rejected_count', 0),
        'top_categories': [x.get('category') for x in alerts[:5]],
        'briefing_categories': [x.get('category') for x in briefing_items[:5]],
    }
    with HISTORY_FILE.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + '\n')

    entries = []
    try:
        with HISTORY_FILE.open('r', encoding='utf-8') as fh:
            entries = [json.loads(line) for line in fh if line.strip()]
    except FileNotFoundError:
        pass

    metrics = {
        'runs': len(entries),
        'avg_alert_count': round(sum(x.get('alert_count', 0) for x in entries) / max(1, len(entries)), 2),
        'avg_approved_count': round(sum(x.get('approved_count', 0) for x in entries) / max(1, len(entries)), 2),
        'last_governance_mode': entry['governance_mode'],
        'last_run_utc': entry['ts_utc'],
    }
    METRICS_FILE.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    return metrics
