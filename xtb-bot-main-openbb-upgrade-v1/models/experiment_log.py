from pathlib import Path
import json
import datetime as dt

FILE = Path(".state/block4_experiments.json")
FILE.parent.mkdir(parents=True, exist_ok=True)

def log_experiment(payload):
    data = []
    if FILE.exists():
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    data.append({"timestamp": dt.datetime.utcnow().isoformat(), "payload": payload})
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
