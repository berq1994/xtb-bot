from pathlib import Path
import json
import datetime as dt

REG = Path(".state/model_registry.json")
REG.parent.mkdir(parents=True, exist_ok=True)

def load_registry():
    if not REG.exists():
        return {"active_models": [], "history": []}
    try:
        return json.loads(REG.read_text(encoding="utf-8"))
    except Exception:
        return {"active_models": [], "history": []}

def register_model(name: str, metrics: dict):
    reg = load_registry()
    reg["active_models"] = [m for m in reg.get("active_models", []) if m.get("name") != name]
    reg["active_models"].append({"name": name, "metrics": metrics, "updated_at": dt.datetime.utcnow().isoformat()})
    reg.setdefault("history", []).append({"name": name, "metrics": metrics, "updated_at": dt.datetime.utcnow().isoformat()})
    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return reg
