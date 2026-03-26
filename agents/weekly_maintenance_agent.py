from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

TIMEZONE = 'Europe/Prague'
REPORT_PATH = Path('weekly_maintenance_report.txt')
STATE_RETENTION_DAYS = 30
JSONL_KEEP_LINES = 4000


def _now_local() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    try:
        return datetime.now(ZoneInfo(TIMEZONE))
    except Exception:
        return datetime.now()


def _prune_state_mapping(path: Path, key_name: str, date_field: str) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return 0, 0
    if not isinstance(payload, dict):
        return 0, 0
    mapping = payload.get(key_name, {})
    if not isinstance(mapping, dict):
        return 0, 0
    before = len(mapping)
    cutoff = _now_local() - timedelta(days=STATE_RETENTION_DAYS)
    kept: dict[str, Any] = {}
    for key, row in mapping.items():
        if not isinstance(row, dict):
            continue
        raw = str(row.get(date_field, '') or '')
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except Exception:
            kept[key] = row
            continue
        if dt.tzinfo is None:
            kept[key] = row
            continue
        if cutoff.astimezone(dt.tzinfo) - dt <= timedelta(0):
            kept[key] = row
    payload[key_name] = kept
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return before, len(kept)


def _trim_jsonl(path: Path, keep_lines: int = JSONL_KEEP_LINES) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    lines = [line for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    before = len(lines)
    if before <= keep_lines:
        return before, before
    trimmed = lines[-keep_lines:]
    path.write_text('\n'.join(trimmed) + '\n', encoding='utf-8')
    return before, len(trimmed)


def _remove_if_exists(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        path.unlink()
        return True
    except Exception:
        return False


def run_weekly_maintenance() -> str:
    lines: list[str] = []
    lines.append('WEEKLY MAINTENANCE')
    lines.append(f'Čas: {_now_local().strftime("%d.%m.%Y %H:%M %Z")}')
    lines.append('')

    for path, key_name, date_field, label in [
        (Path('.state/delivery/portfolio_telegram_alert_state.json'), 'last_by_symbol', 'sent_at', 'Telegram cooldown stav'),
        (Path('.state/autonomous_core_state.json'), 'last_signal_by_key', 'sent_at', 'Autonomní cooldown stav'),
    ]:
        before, after = _prune_state_mapping(path, key_name, date_field)
        lines.append(f'- {label}: {before} -> {after}')

    for path, label in [
        (Path('data/openbb_signal_history.jsonl'), 'Historie signálů'),
        (Path('data/outcome_tracking.jsonl'), 'Outcome tracking'),
    ]:
        before, after = _trim_jsonl(path)
        lines.append(f'- {label}: {before} -> {after} řádků')

    removed_budget = _remove_if_exists(Path('.state/fmp_budget.json'))
    reset_label = 'ano' if removed_budget else 'ne / nic k resetu'
    lines.append(f'- Reset FMP budget cache: {reset_label}')

    output = '\n'.join(lines)
    REPORT_PATH.write_text(output, encoding='utf-8')
    return output
