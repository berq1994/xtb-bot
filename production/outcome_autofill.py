import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from production.fmp_market_data import fetch_eod_series, fetch_intraday_series, nearest_price, next_eod_price

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


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    txt = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(txt, fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def _pct_move(entry: Optional[float], current: Optional[float]) -> Optional[float]:
    if entry in (None, 0) or current is None:
        return None
    return round(((float(current) / float(entry)) - 1.0) * 100.0, 4)


def _threshold_for(row: Dict[str, Any]) -> float:
    priority = str(row.get("priority", "MEDIUM")).upper()
    status = str(row.get("status", "")).upper()
    if priority == "HIGH":
        return 1.25
    if status == "HIGH VOL":
        return 1.00
    if priority == "LOW":
        return 0.75
    return 0.90


def _compute_directional_hit(row: Dict[str, Any]) -> Optional[bool]:
    candidates = [
        row.get("outcome_15m"),
        row.get("outcome_60m"),
        row.get("outcome_1d"),
    ]
    usable = [abs(float(x)) for x in candidates if x is not None]
    if not usable:
        return None
    return max(usable) >= _threshold_for(row)


def _apply_manual_updates(rows: List[Dict[str, Any]], updates: List[Dict[str, Any]]) -> Tuple[int, int, List[str]]:
    applied = 0
    unmatched_updates = 0
    touched_ids: List[str] = []

    if not updates:
        return applied, unmatched_updates, touched_ids

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
            row["autofill_source"] = "manual_update"
            if "record_id" in row:
                touched_ids.append(str(row["record_id"]))
            applied += 1
        if not matched_any:
            unmatched_updates += 1
    return applied, unmatched_updates, touched_ids


def _autofill_from_fmp(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    intraday_cache: Dict[str, List[Dict[str, Any]]] = {}
    eod_cache: Dict[str, List[Dict[str, Any]]] = {}
    updated = 0
    attempted = 0
    touched_ids: List[str] = []

    for row in rows:
        if row.get("directional_hit") is not None:
            continue
        ticker = str(row.get("primary_ticker") or (row.get("tickers") or [None])[0] or "").upper().strip()
        recorded_at = _parse_dt(str(row.get("recorded_at", "")))
        if not ticker or not recorded_at:
            continue
        attempted += 1

        if ticker not in intraday_cache:
            intraday_cache[ticker] = fetch_intraday_series(ticker, interval="5min", days_back=3)
        if ticker not in eod_cache:
            eod_cache[ticker] = fetch_eod_series(ticker, days_back=10)

        intraday = intraday_cache[ticker]
        eod = eod_cache[ticker]

        entry_price = row.get("entry_price")
        if entry_price is None:
            entry_price = nearest_price(intraday, recorded_at, mode="closest")
            if entry_price is not None:
                row["entry_price"] = round(float(entry_price), 4)
                row["entry_price_source"] = "fmp_intraday_nearest"

        if entry_price is None:
            continue

        p15 = nearest_price(intraday, recorded_at + timedelta(minutes=15), mode="after")
        p60 = nearest_price(intraday, recorded_at + timedelta(minutes=60), mode="after")
        p1d = next_eod_price(eod, recorded_at + timedelta(days=1))

        row["outcome_15m"] = _pct_move(entry_price, p15)
        row["outcome_60m"] = _pct_move(entry_price, p60)
        row["outcome_1d"] = _pct_move(entry_price, p1d)
        row["directional_hit"] = _compute_directional_hit(row)
        row["resolution_note"] = row.get("resolution_note") or "Autofill přes FMP intraday/EOD ceny."
        row["autofill_source"] = "fmp_market_data"
        row["autofill_ticker"] = ticker
        row["autofill_recorded_at"] = recorded_at.isoformat()
        updated += 1
        if row.get("record_id"):
            touched_ids.append(str(row["record_id"]))

    return {
        "fmp_attempted": attempted,
        "fmp_applied": updated,
        "fmp_touched_record_ids": touched_ids[:50],
        "symbols_used": sorted([k for k, v in intraday_cache.items() if v or eod_cache.get(k)]),
    }


def apply_outcome_updates(registry_path: str | Path = REGISTRY_PATH, summary_path: str | Path = SUMMARY_PATH) -> Dict[str, Any]:
    rows = _read_jsonl(Path(registry_path))
    updates, source_path = _load_update_payload()

    manual_applied, unmatched_updates, touched_ids = _apply_manual_updates(rows, updates)
    fmp_result = _autofill_from_fmp(rows)
    applied = manual_applied + int(fmp_result.get("fmp_applied", 0))

    if updates or fmp_result.get("fmp_applied"):
        _write_jsonl(Path(registry_path), rows)

    payload = {
        "update_source": source_path,
        "updates_found": len(updates),
        "applied_updates": applied,
        "manual_applied_updates": manual_applied,
        "fmp_applied_updates": int(fmp_result.get("fmp_applied", 0)),
        "fmp_attempted": int(fmp_result.get("fmp_attempted", 0)),
        "unmatched_updates": unmatched_updates,
        "touched_record_ids": (touched_ids + fmp_result.get("fmp_touched_record_ids", []))[:50],
        "symbols_used": fmp_result.get("symbols_used", []),
    }
    _write_json(Path(summary_path), payload)
    return payload
