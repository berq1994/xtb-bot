import json
from pathlib import Path

def read_governance_snapshot():
    candidates = [
        ".state/block8a_threshold_tuning.json",
        ".state/block6b_final_decision.json",
        ".state/block7c_semi_live.json",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}

def extract_governance_mode(snapshot: dict):
    try:
        return snapshot.get("tuned_decision", {}).get("transition", {}).get("final_mode", "SAFE_MODE")
    except Exception:
        return "SAFE_MODE"
