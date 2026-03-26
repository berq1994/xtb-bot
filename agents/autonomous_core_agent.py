from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agents.autonomous_learning_loop_agent import run_autonomous_learning_loop
from agents.knowledge_ingestion_agent import run_knowledge_sync
from agents.learning_agent import load_signal_weights, run_learning_review, run_rebalance_weights
from agents.live_research_agent import run_live_research
from agents.outcome_tracking_agent import OUTCOME_PATH, run_outcome_review, run_outcome_update
from agents.signal_history_agent import build_snapshot_payload, append_history_entry

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

TIMEZONE = os.getenv("TIMEZONE", "Europe/Prague")
STATE_PATH = Path('.state/autonomous_core_state.json')
REPORT_PATH = Path('autonomous_core_report.txt')
MIN_RESOLVED_FOR_REBALANCE = int(os.getenv('AUTO_REBALANCE_MIN_RESOLVED', '8') or 8)
REBALANCE_COOLDOWN_HOURS = int(os.getenv('AUTO_REBALANCE_COOLDOWN_HOURS', '24') or 24)
SIGNAL_COOLDOWN_MIN = int(os.getenv('AUTO_SIGNAL_COOLDOWN_MIN', '180') or 180)
TOP_N_SIGNALS = int(os.getenv('AUTO_SIGNAL_TOP_N', '2') or 2)


def _now_local() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    try:
        return datetime.now(ZoneInfo(TIMEZONE))
    except Exception:
        return datetime.now()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def _resolved_count() -> int:
    rows = _load_jsonl(OUTCOME_PATH)
    return sum(1 for row in rows if row.get('outcome_label') in {'win', 'loss', 'flat'})


def _history_recent_same(symbol: str, category: str, state: dict[str, Any], now_local: datetime) -> bool:
    saved = state.get('last_signal_by_key', {}) if isinstance(state.get('last_signal_by_key'), dict) else {}
    key = f'{symbol}|{category}'
    row = saved.get(key, {}) if isinstance(saved.get(key), dict) else {}
    sent_at = _parse_dt(row.get('sent_at'))
    if not sent_at:
        return False
    if sent_at.tzinfo is None:
        return False
    return now_local.astimezone(sent_at.tzinfo) - sent_at < timedelta(minutes=SIGNAL_COOLDOWN_MIN)


def _remember_signal(symbol: str, category: str, state: dict[str, Any], now_local: datetime) -> None:
    state.setdefault('last_signal_by_key', {})[f'{symbol}|{category}'] = {
        'sent_at': now_local.isoformat(),
    }


def _auto_log_top_research_items(state: dict[str, Any]) -> list[str]:
    research_state = _load_json(Path('data/research_live_state.json'))
    top_items = research_state.get('top_items', []) if isinstance(research_state, dict) else []
    now_local = _now_local()
    logged: list[str] = []
    for item in top_items[:TOP_N_SIGNALS]:
        symbol = str(item.get('symbol', '')).strip().upper()
        category = str(item.get('category', 'watchlist_monitor')).strip() or 'watchlist_monitor'
        if not symbol:
            continue
        if _history_recent_same(symbol, category, state, now_local):
            continue
        payload = build_snapshot_payload(research_state, ticket_symbol=symbol)
        if payload.get('ticket_symbol') != symbol:
            payload['ticket_symbol'] = symbol
            payload.setdefault('ticket', {})['symbol'] = symbol
        payload['supervisor'] = dict(payload.get('supervisor') or {})
        payload['supervisor']['autonomous'] = True
        payload['supervisor']['autonomous_reason'] = category
        payload['supervisor']['logged_by'] = 'autonomous_core'
        payload['autonomous'] = {
            'core_cycle': True,
            'category': category,
            'priority_score': item.get('priority_score'),
            'evidence_grade': item.get('evidence_grade'),
        }
        append_history_entry(payload)
        _remember_signal(symbol, category, state, now_local)
        logged.append(symbol)
    return logged


def _should_rebalance(state: dict[str, Any], now_local: datetime, resolved_count: int) -> bool:
    if resolved_count < MIN_RESOLVED_FOR_REBALANCE:
        return False
    last = _parse_dt(str(state.get('last_rebalance_at') or ''))
    if last is None:
        return True
    if last.tzinfo is None:
        return True
    return now_local.astimezone(last.tzinfo) - last >= timedelta(hours=REBALANCE_COOLDOWN_HOURS)


def run_autonomous_core() -> str:
    state = _load_json(STATE_PATH)
    now_local = _now_local()
    before_weights = load_signal_weights()

    knowledge_sync = run_knowledge_sync()
    research_report = run_live_research()
    auto_logged = _auto_log_top_research_items(state)
    outcome_update = run_outcome_update()
    outcome_review = run_outcome_review()
    learning_review = run_learning_review()
    autonomous_learning = run_autonomous_learning_loop()

    resolved_count = _resolved_count()
    rebalanced = False
    rebalance_report = 'Rebalance vah přeskočen.'
    if _should_rebalance(state, now_local, resolved_count):
        rebalance_report = run_rebalance_weights(limit=80)
        rebalanced = True
        state['last_rebalance_at'] = now_local.isoformat()

    after_weights = load_signal_weights()
    state['last_cycle_at'] = now_local.isoformat()
    state['last_logged_symbols'] = auto_logged
    state['resolved_count_at_cycle'] = resolved_count
    _save_json(STATE_PATH, state)

    rebalance_status = 'proveden' if rebalanced else 'neproveden'
    lines = [
        'AUTONOMNÍ JÁDRO',
        f'Čas: {now_local.strftime("%d.%m.%Y %H:%M %Z")}',
        f'Automaticky zapsané signály: {", ".join(auto_logged) if auto_logged else "žádné nové"}',
        f'Vyhodnocené outcome vzorky: {resolved_count}',
        f'Rebalance vah: {rebalance_status}',
        f'Nízkovolací FMP režim: {'ano' if str(os.getenv('FMP_LOW_CALL_MODE', '0')).strip().lower() in {'1','true','yes','on'} else 'ne'}',
        '',
        'VÁHY PŘED -> PO',
    ]
    for key in sorted(after_weights):
        lines.append(f'- {key}: {before_weights.get(key)} -> {after_weights.get(key)}')
    lines.extend([
        '',
        'KNOWLEDGE SYNC',
        knowledge_sync.strip(),
        '',
        'STRUČNÝ STAV',
        research_report.strip(),
        '',
        outcome_update.strip(),
        '',
        outcome_review.strip(),
        '',
        learning_review.strip(),
        '',
        autonomous_learning.strip(),
        '',
        rebalance_report.strip(),
    ])
    output = '\n'.join(lines)
    REPORT_PATH.write_text(output, encoding='utf-8')
    return output
