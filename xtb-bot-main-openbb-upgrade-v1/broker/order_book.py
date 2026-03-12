from pathlib import Path
import json

FILE = Path(".state/broker_order_book.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def load_order_book():
    if FILE.exists():
        try:
            return json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def save_order(order_row: dict):
    rows = load_order_book()
    rows.append(order_row)
    FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows
