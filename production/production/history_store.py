import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

HISTORY_DIR = Path(".state/history")
RUN_HISTORY_PATH = HISTORY_DIR / "block14_history.jsonl"
RUN_METRICS_PATH = HISTORY_DIR / "block14_metrics.json"


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def archive_run(
    payload: Dict[str, Any],
    alerts: List[Dict[str, Any]],
    briefing_items: List[Dict[str, Any]],
    evaluation: Dict[str, Any],
    critic: Dict[str, Any] | None = None,
    decision: Dict[str, Any] | None = None,
    tracker_summary: Dict[str, Any] | None = None,
    performance_summary: Dict[str, Any] | None = None,
    risk_overlay: Dict[str, Any] | None = None,
    execution_guard: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(x.get("status", "UNKNOWN") for x in alerts)
    entry = {
        "ts_utc": _utc_now_iso(),
        "governance_mode": payload.get("report", {}).get("governance_mode"),
        "alert_count": len(alerts),
        "approved_count": evaluation.get("approved_count", 0),
        "rejected_count": evaluation.get("rejected_count", 0),
        "critic_approved_count": (critic or {}).get("approved_count", 0),
        "critic_rejected_count": (critic or {}).get("rejected_count", 0),
        "top_categories": [x.get("category") for x in alerts[:5]],
        "briefing_categories": [x.get("category") for x in briefing_items[:5]],
        "status_counts": dict(status_counts),
        "recommended_mode": (decision or {}).get("recommended_mode", "NORMAL"),
        "tracker_records": (tracker_summary or {}).get("records", 0),
        "tracker_pending": (tracker_summary or {}).get("pending_records", 0),
        "performance_hit_rate": (performance_summary or {}).get("overall_hit_rate", 0.0),
        "risk_posture": (risk_overlay or {}).get("risk_posture", "NORMAL"),
        "kill_switch_armed": bool((risk_overlay or {}).get("kill_switch_armed", False)),
        "guard_status": (execution_guard or {}).get("guard_status", "MANUAL_ONLY"),
        "allow_new_risk": bool((execution_guard or {}).get("allow_new_risk", False)),
    }
    _append_jsonl(RUN_HISTORY_PATH, entry)

    entries = _read_jsonl(RUN_HISTORY_PATH)
    aggregate_status = Counter()
    recommended_mode_counts = Counter()
    risk_posture_counts = Counter()
    guard_status_counts = Counter()
    allow_new_risk_runs = 0
    kill_switch_runs = 0

    for item in entries:
        aggregate_status.update(item.get("status_counts", {}))
        recommended_mode_counts[item.get("recommended_mode", "UNKNOWN")] += 1
        risk_posture_counts[item.get("risk_posture", "UNKNOWN")] += 1
        guard_status_counts[item.get("guard_status", "UNKNOWN")] += 1
        if item.get("allow_new_risk"):
            allow_new_risk_runs += 1
        if item.get("kill_switch_armed"):
            kill_switch_runs += 1

    metrics = {
        "runs": len(entries),
        "avg_alert_count": round(sum(x.get("alert_count", 0) for x in entries) / max(1, len(entries)), 2),
        "avg_approved_count": round(sum(x.get("approved_count", 0) for x in entries) / max(1, len(entries)), 2),
        "avg_critic_approved_count": round(sum(x.get("critic_approved_count", 0) for x in entries) / max(1, len(entries)), 2),
        "last_governance_mode": entry["governance_mode"],
        "last_run_utc": entry["ts_utc"],
        "recommended_mode": entry["recommended_mode"],
        "recommended_mode_counts": dict(recommended_mode_counts),
        "status_counts": dict(aggregate_status),
        "latest_tracker_records": entry["tracker_records"],
        "latest_tracker_pending": entry["tracker_pending"],
        "latest_performance_hit_rate": entry["performance_hit_rate"],
        "risk_posture_counts": dict(risk_posture_counts),
        "guard_status_counts": dict(guard_status_counts),
        "allow_new_risk_runs": allow_new_risk_runs,
        "kill_switch_runs": kill_switch_runs,
        "latest_risk_posture": entry["risk_posture"],
        "latest_guard_status": entry["guard_status"],
    }
    _write_json(RUN_METRICS_PATH, metrics)
    return metrics


def load_run_metrics(path: str | Path = RUN_METRICS_PATH) -> Dict[str, Any]:
    return _read_json(Path(path), default={})


def load_run_history(path: str | Path = RUN_HISTORY_PATH) -> List[Dict[str, Any]]:
    return _read_jsonl(Path(path))
