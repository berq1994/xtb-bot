import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

REGISTRY_PATH = Path(".state/history/alert_registry.jsonl")
SUMMARY_PATH = Path(".state/history/alert_autofill_summary.json")
CANDIDATE_UPDATE_FILES = [
    Path("outcome_updates.json"),
    Path(".state/outcome_updates.json"),
    Path(".state/history/outcome_updates.json"),
    Path("outcome_prices.json"),
    Path(".state/outcome_prices.json"),
    Path(".state/history/outcome_prices.json"),
]


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


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_update_payload() -> Tuple[List[Dict[str, Any]], str | None]:
    for path in CANDIDATE_UPDATE_FILES:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            updates = payload.get("updates") or payload.get("registry_updates") or []
            if isinstance(updates, list):
                return updates, str(path)
        elif isinstance(payload, list):
            return payload, str(path)
    return [], None


def _match_update(row: Dict[str, Any], update: Dict[str, Any]) -> bool:
    title = str(row.get("title", "")).lower()
    category = str(row.get("category", "")).lower()
    tickers = {str(x).upper() for x in row.get("tickers", [])}
    rec_id = str(row.get("record_id", ""))

    if update.get("record_id") and str(update.get("record_id")) == rec_id:
        return True
    if update.get("ticker") and str(update.get("ticker")).upper() in tickers:
        return True
    if update.get("category") and str(update.get("category")).lower() == category:
        title_contains = str(update.get("title_contains", "")).lower().strip()
        return bool(title_contains) and title_contains in title
    if update.get("title_contains") and str(update.get("title_contains")).lower() in title:
        return True
    return False


def apply_outcome_updates(registry_path: str | Path = REGISTRY_PATH, summary_path: str | Path = SUMMARY_PATH) -> Dict[str, Any]:
    rows = _read_jsonl(Path(registry_path))
    updates, source_path = _load_update_payload()

    applied = 0
    touched_ids: List[str] = []
    unmatched_updates = 0

    if updates:
        for update in updates:
            matched_any = False
            for row in rows:
                if row.get("directional_hit") is not None:
                    continue
                if not _match_update(row, update):
                    continue
                matched_any = True
                for field in ("outcome_15m", "outcome_60m", "outcome_1d", "directional_hit", "resolution_note"):
                    if field in update:
                        row[field] = update[field]
                if "record_id" in row:
                    touched_ids.append(str(row["record_id"]))
                applied += 1
            if not matched_any:
                unmatched_updates += 1
        _write_jsonl(Path(registry_path), rows)

    payload = {
        "update_source": source_path,
        "updates_found": len(updates),
        "applied_updates": applied,
        "unmatched_updates": unmatched_updates,
        "touched_record_ids": touched_ids[:50],
    }
    _write_json(Path(summary_path), payload)
    return payload
