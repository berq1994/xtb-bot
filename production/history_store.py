import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


HISTORY_DIR = Path(".state/history")
RUN_HISTORY_PATH = HISTORY_DIR / "block14_history.jsonl"
RUN_METRICS_PATH = HISTORY_DIR / "block14_metrics.json"
ALERT_REGISTRY_PATH = HISTORY_DIR / "alert_registry.jsonl"
ALERT_REGISTRY_SUMMARY_PATH = HISTORY_DIR / "alert_registry_summary.json"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _read_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default or {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def archive_run(entry: Dict[str, Any], path: str | Path = RUN_HISTORY_PATH) -> None:
    """
    Zapíše jeden běh do JSONL historie.
    """
    target = Path(path)
    payload = dict(entry)
    payload.setdefault("archived_at", _utc_now_iso())
    _append_jsonl(target, payload)


def load_run_history(path: str | Path = RUN_HISTORY_PATH) -> List[Dict[str, Any]]:
    return _read_jsonl(Path(path))


def update_run_metrics(
    entry: Dict[str, Any],
    history_path: str | Path = RUN_HISTORY_PATH,
    metrics_path: str | Path = RUN_METRICS_PATH,
) -> Dict[str, Any]:
    """
    Aktualizuje souhrnné metriky běhů.
    """
    history_target = Path(history_path)
    metrics_target = Path(metrics_path)

    archive_run(entry, history_target)
    rows = _read_jsonl(history_target)

    recommended_mode_counts = Counter()
    status_counts = Counter()

    approved_total = 0
    rejected_total = 0

    for row in rows:
        mode = str(row.get("recommended_mode", "UNKNOWN"))
        recommended_mode_counts[mode] += 1

        for status, count in (row.get("status_counts") or {}).items():
            try:
                status_counts[str(status)] += int(count)
            except (TypeError, ValueError):
                continue

        critic = row.get("critic_summary") or {}
        try:
            approved_total += int(critic.get("approved_count", 0))
        except (TypeError, ValueError):
            pass
        try:
            rejected_total += int(critic.get("rejected_count", 0))
        except (TypeError, ValueError):
            pass

    payload: Dict[str, Any] = {
        "updated_at": _utc_now_iso(),
        "total_runs": len(rows),
        "last_run_at": rows[-1].get("archived_at") if rows else None,
        "approved_total": approved_total,
        "rejected_total": rejected_total,
        "recommended_mode_counts": dict(recommended_mode_counts),
        "status_counts": dict(status_counts),
    }

    _write_json(metrics_target, payload)
    return payload


def load_run_metrics(path: str | Path = RUN_METRICS_PATH) -> Dict[str, Any]:
    return _read_json(Path(path), default={})


def archive_alert_registry(
    alerts: Iterable[Dict[str, Any]],
    path: str | Path = ALERT_REGISTRY_PATH,
) -> int:
    """
    Zapíše alerty do registru pro pozdější outcome tracking.
    """
    target = Path(path)
    written = 0

    for alert in alerts:
        payload = dict(alert)
        payload.setdefault("recorded_at", _utc_now_iso())
        _append_jsonl(target, payload)
        written += 1

    return written


def load_alert_registry(path: str | Path = ALERT_REGISTRY_PATH) -> List[Dict[str, Any]]:
    return _read_jsonl(Path(path))


def update_alert_registry_summary(
    registry_path: str | Path = ALERT_REGISTRY_PATH,
    summary_path: str | Path = ALERT_REGISTRY_SUMMARY_PATH,
) -> Dict[str, Any]:
    """
    Vytvoří jednoduchý souhrn registru alertů.
    """
    rows = _read_jsonl(Path(registry_path))

    category_counts = Counter()
    priority_counts = Counter()
    status_counts = Counter()
    bias_counts = Counter()
    timeframe_counts = Counter()

    for row in rows:
        category_counts[str(row.get("category", "unknown")).upper()] += 1
        priority_counts[str(row.get("priority", "unknown")).upper()] += 1
        status_counts[str(row.get("status", "unknown")).upper()] += 1
        bias_counts[str(row.get("bias", "unknown"))] += 1
        timeframe_counts[str(row.get("timeframe", "unknown"))] += 1

    payload: Dict[str, Any] = {
        "updated_at": _utc_now_iso(),
        "total_alerts": len(rows),
        "category_counts": dict(category_counts),
        "priority_counts": dict(priority_counts),
        "status_counts": dict(status_counts),
        "bias_counts": dict(bias_counts),
        "timeframe_counts": dict(timeframe_counts),
    }

    _write_json(Path(summary_path), payload)
    return payload