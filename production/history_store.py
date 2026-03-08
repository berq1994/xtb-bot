import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

HISTORY_DIR = Path('.state/history')
HISTORY_FILE = HISTORY_DIR / 'block14_history.jsonl'
METRICS_FILE = HISTORY_DIR / 'block14_metrics.json'


def archive_run(payload: Dict, alerts: List[Dict], briefing_items: List[Dict], evaluation: Dict, critic: Dict | None = None, decision: Dict | None = None) -> Dict:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(x.get('status', 'UNKNOWN') for x in alerts)
    entry = {
        'ts_utc': datetime.now(timezone.utc).isoformat(),
        'governance_mode': payload.get('report', {}).get('governance_mode'),
        'alert_count': len(alerts),
        'approved_count': evaluation.get('approved_count', 0),
        'rejected_count': evaluation.get('rejected_count', 0),
        'critic_approved_count': (critic or {}).get('approved_count', 0),
        'critic_rejected_count': (critic or {}).get('rejected_count', 0),
        'top_categories': [x.get('category') for x in alerts[:5]],
        'briefing_categories': [x.get('category') for x in briefing_items[:5]],
        'status_counts': dict(status_counts),
        'recommended_mode': (decision or {}).get('recommended_mode', 'NORMAL'),
    }
    with HISTORY_FILE.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + '
')

    entries = []
    if HISTORY_FILE.exists():
        with HISTORY_FILE.open('r', encoding='utf-8') as fh:
            entries = [json.loads(line) for line in fh if line.strip()]

    aggregate_status = Counter()
    for item in entries:
        aggregate_status.update(item.get('status_counts', {}))

    metrics = {
        'runs': len(entries),
        'avg_alert_count': round(sum(x.get('alert_count', 0) for x in entries) / max(1, len(entries)), 2),
        'avg_approved_count': round(sum(x.get('approved_count', 0) for x in entries) / max(1, len(entries)), 2),
        'avg_critic_approved_count': round(sum(x.get('critic_approved_count', 0) for x in entries) / max(1, len(entries)), 2),
        'last_governance_mode': entry['governance_mode'],
        'last_run_utc': entry['ts_utc'],
        'recommended_mode': entry['recommended_mode'],
        'status_counts': dict(aggregate_status),
    }
    METRICS_FILE.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    return metrics
