import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


OUTCOME_DIR = Path(".state/history")
ALERT_REGISTRY_PATH = OUTCOME_DIR / "alert_registry.jsonl"
ALERT_REGISTRY_SUMMARY_PATH = OUTCOME_DIR / "alert_registry_summary.json"


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


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_record_id(alert: Dict[str, Any], idx: int) -> str:
    category = str(alert.get("category", "unknown")).lower()
    title = str(alert.get("title", "untitled")).lower().replace(" ", "-")[:40]
    return f"{_utc_now_iso()}::{idx}::{category}::{title}"


def register_alerts(
    alerts: Iterable[Dict[str, Any]],
    path: str | Path = ALERT_REGISTRY_PATH,
) -> int:
    """
    Zapíše alerty do registru pro pozdější vyhodnocení.
    """
    target = Path(path)
    written = 0

    for idx, alert in enumerate(alerts, start=1):
        payload = dict(alert)
        payload.setdefault("recorded_at", _utc_now_iso())
        payload.setdefault("record_id", _build_record_id(payload, idx))
        payload.setdefault("outcome_15m", None)
        payload.setdefault("outcome_60m", None)
        payload.setdefault("outcome_1d", None)
        payload.setdefault("directional_hit", None)
        payload.setdefault("resolution_note", None)
        _append_jsonl(target, payload)
        written += 1

    return written


def load_registered_alerts(path: str | Path = ALERT_REGISTRY_PATH) -> List[Dict[str, Any]]:
    return _read_jsonl(Path(path))


def summarize_registry(
    registry_path: str | Path = ALERT_REGISTRY_PATH,
    summary_path: str | Path = ALERT_REGISTRY_SUMMARY_PATH,
) -> Dict[str, Any]:
    rows = _read_jsonl(Path(registry_path))

    by_category: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    by_bias: Dict[str, int] = {}
    by_timeframe: Dict[str, int] = {}
    scored = 0
    pending = 0

    for row in rows:
        category = str(row.get("category", "unknown")).upper()
        priority = str(row.get("priority", "unknown")).upper()
        status = str(row.get("status", "unknown")).upper()
        bias = str(row.get("bias", "unknown"))
        timeframe = str(row.get("timeframe", "unknown"))

        by_category[category] = by_category.get(category, 0) + 1
        by_priority[priority] = by_priority.get(priority, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        by_bias[bias] = by_bias.get(bias, 0) + 1
        by_timeframe[timeframe] = by_timeframe.get(timeframe, 0) + 1

        if row.get("directional_hit") is None:
            pending += 1
        else:
            scored += 1

    payload: Dict[str, Any] = {
        "updated_at": _utc_now_iso(),
        "total_alerts": len(rows),
        "scored_alerts": scored,
        "pending_alerts": pending,
        "by_category": by_category,
        "by_priority": by_priority,
        "by_status": by_status,
        "by_bias": by_bias,
        "by_timeframe": by_timeframe,
    }

    _write_json(Path(summary_path), payload)
    return payload
