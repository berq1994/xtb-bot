import json
from pathlib import Path

def _read_json(path_str: str, default):
    p = Path(path_str)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
    return default

def build_activation_suite():
    d = _read_json(".state/block16a_real_delivery.json", {})
    s = _read_json(".state/block16b_real_sources_activation.json", {})
    return {
        "delivery": d,
        "sources": s,
        "telegram_ok": bool(d.get("telegram", {}).get("delivered", False)),
        "email_ok": bool(d.get("email", {}).get("delivered", False)),
        "sources_ok_count": sum(
            1 for k in ["gdelt", "sec", "earnings", "macro"]
            if s.get(k, {}).get("ok", False)
        ),
    }
