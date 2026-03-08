import json
from pathlib import Path
from typing import Any, Dict, List

from production.outcome_autofill import apply_outcome_updates

REGISTRY_PATH = Path(".state/history/alert_registry.jsonl")
SUMMARY_PATH = Path(".state/history/alert_performance_summary.json")


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_performance() -> Dict[str, Any]:
    try:
        autofill_summary = apply_outcome_updates()
    except Exception as exc:
        autofill_summary = {
            "applied_updates": 0,
            "manual_applied_updates": 0,
            "fmp_applied_updates": 0,
            "fmp_attempted": 0,
            "fmp_skipped_errors": 0,
            "error": str(exc),
        }
    rows = _read_jsonl(REGISTRY_PATH)

    total_records = len(rows)
    scored_records = 0
    pending_records = 0
    directional_hits = 0
    with_entry_price = 0

    by_category: Dict[str, Dict[str, float]] = {}
    by_status: Dict[str, Dict[str, float]] = {}
    by_priority: Dict[str, Dict[str, float]] = {}

    for row in rows:
        category = str(row.get("category", "unknown")).upper()
        status = str(row.get("status", "unknown")).upper()
        priority = str(row.get("priority", "unknown")).upper()

        if row.get("entry_price") is not None:
            with_entry_price += 1

        hit = row.get("directional_hit")
        if hit is None:
            pending_records += 1
        else:
            scored_records += 1
            if bool(hit):
                directional_hits += 1

        for bucket_name, bucket_key in [
            ("by_category", category),
            ("by_status", status),
            ("by_priority", priority),
        ]:
            bucket = {"by_category": by_category, "by_status": by_status, "by_priority": by_priority}[bucket_name]
            bucket.setdefault(bucket_key, {"total": 0, "scored": 0, "hits": 0})
            bucket[bucket_key]["total"] += 1
            if hit is not None:
                bucket[bucket_key]["scored"] += 1
                if bool(hit):
                    bucket[bucket_key]["hits"] += 1

    overall_hit_rate = round((directional_hits / scored_records), 4) if scored_records else 0.0

    for bucket in (by_category, by_status, by_priority):
        for _, value in bucket.items():
            scored = value["scored"]
            value["hit_rate"] = round((value["hits"] / scored), 4) if scored else 0.0

    payload = {
        "total_records": total_records,
        "pending_records": pending_records,
        "scored_records": scored_records,
        "overall_hit_rate": overall_hit_rate,
        "records_with_entry_price": with_entry_price,
        "autofill_summary": autofill_summary,
        "by_category": by_category,
        "by_status": by_status,
        "by_priority": by_priority,
    }

    _write_json(SUMMARY_PATH, payload)
    return payload
