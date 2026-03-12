import json
from pathlib import Path

def _read_json(path_str, default):
    path = Path(path_str)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default

def load_live_intelligence_rows():
    b12a = _read_json(".state/block12a_live_intelligence.json", {"rows": []})
    rows = b12a.get("rows", [])
    if rows:
        return rows

    return [
        {
            "kind": "geo",
            "headline": "Fallback geopolitická událost",
            "summary_cz": "Fallback intelligence.",
            "tickers": ["CVX"],
            "sectors": ["Energy"],
            "relevance": 0.8,
            "impact": 0.78,
        }
    ]
