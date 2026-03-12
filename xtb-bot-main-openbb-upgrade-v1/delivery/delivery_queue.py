from pathlib import Path
import json

FILE = Path(".state/delivery_queue.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def enqueue(kind: str, message: str):
    rows = []
    if FILE.exists():
        try:
            rows = json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    rows.append({"kind": kind, "message": message})
    FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows
