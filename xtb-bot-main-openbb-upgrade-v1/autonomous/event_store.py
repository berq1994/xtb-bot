from pathlib import Path
import json
import hashlib
import datetime as dt

FILE = Path(".state/autonomous_event_store.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def load_event_store():
    if FILE.exists():
        try:
            return json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"events": []}

def _event_id(item: dict):
    raw = f"{item.get('kind')}|{item.get('headline')}|{','.join(item.get('tickers', []))}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def store_events(items: list):
    db = load_event_store()
    existing_ids = {x.get("event_id") for x in db.get("events", [])}
    new_rows = []

    for item in items:
        eid = _event_id(item)
        row = {
            "event_id": eid,
            "stored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            **item,
        }
        if eid not in existing_ids:
            db["events"].append(row)
            new_rows.append(row)

    FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"new_events": new_rows, "total_events": len(db.get("events", []))}
