from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agents.portfolio_context_agent import load_portfolio_symbols
from agents.technical_analysis_agent import build_technical_analysis_map

REPORT_PATH = Path('weekly_ta_rebuild_report.txt')
SNAPSHOT_PATH = Path('data/weekly_ta_rebuild_snapshot.json')


def run_weekly_ta_rebuild() -> str:
    symbols = load_portfolio_symbols(limit=25)
    ta_map = build_technical_analysis_map(symbols)
    snapshot = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'count': len(ta_map),
        'symbols': ta_map,
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['TÝDENNÍ TA REBUILD', f'Počet symbolů: {len(ta_map)}']
    for symbol, item in list(ta_map.items())[:12]:
        lines.append(f"- {symbol} | trend {item.get('trend_regime')} | setup {item.get('setup_type')} | akce {item.get('buy_decision')} | support {item.get('support', '-')} | rezistence {item.get('resistance', '-')}")
    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding='utf-8')
    return report
