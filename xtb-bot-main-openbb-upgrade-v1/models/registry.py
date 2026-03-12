from pathlib import Path
import json

REG = Path(".state/block4_model_registry.json")
REG.parent.mkdir(parents=True, exist_ok=True)

def load_registry():
    if REG.exists():
        try:
            return json.loads(REG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"models": [], "champion": None}

def save_registry(data):
    REG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
