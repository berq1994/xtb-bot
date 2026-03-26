from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

THESIS_PATH = Path("data/thesis_updates.json")
MEMORY_PATH = Path("data/research_memory.json")
REPORT_PATH = Path("research_memory_report.txt")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_research_memory_update() -> str:
    thesis = _load_json(THESIS_PATH)
    updates = thesis.get("updates", []) if isinstance(thesis, dict) else []
    memory = _load_json(MEMORY_PATH)
    if not isinstance(memory, dict):
        memory = {}

    symbols = memory.get("symbols", {})
    if not isinstance(symbols, dict):
        symbols = {}

    for item in updates:
        symbol = str(item.get("symbol", "")).strip()
        if not symbol:
            continue
        row = symbols.get(
            symbol,
            {
                "mentions": 0,
                "last_action": None,
                "last_thesis_change": None,
                "last_confidence": None,
                "held": False,
                "history": [],
            },
        )
        row["mentions"] = int(row.get("mentions", 0)) + 1
        row["last_action"] = item.get("action")
        row["last_thesis_change"] = item.get("thesis_change")
        row["last_confidence"] = item.get("confidence")
        row["held"] = bool(item.get("held", False))
        history = row.get("history", [])
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": item.get("action"),
                "thesis_change": item.get("thesis_change"),
                "confidence": item.get("confidence"),
                "category": item.get("category"),
            }
        )
        row["history"] = history[-10:]
        symbols[symbol] = row

    memory["last_updated"] = datetime.now(timezone.utc).isoformat()
    memory["regime"] = thesis.get("regime", memory.get("regime", "mixed"))
    memory["source"] = thesis.get("source", memory.get("source", "unknown"))
    memory["symbols"] = dict(sorted(symbols.items()))

    category_counter = Counter()
    for item in updates:
        category_counter[str(item.get("category", "unknown"))] += 1
    memory["last_category_mix"] = dict(category_counter)

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("RESEARCH MEMORY UPDATE")
    lines.append(f"Aktualizováno symbolů: {len(updates)}")
    lines.append(f"Režim trhu: {memory.get('regime', 'mixed')}")
    lines.append("Category mix:")
    if category_counter:
        for key, value in category_counter.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- bez nových dat")
    lines.append("Nejčastěji sledované symboly:")
    most_seen = sorted(memory["symbols"].items(), key=lambda x: int(x[1].get("mentions", 0)), reverse=True)[:5]
    for symbol, row in most_seen:
        lines.append(
            f"- {symbol}: mentions {row.get('mentions', 0)} | action {row.get('last_action', '-')} | thesis {row.get('last_thesis_change', '-')}"
        )
    output = "\n".join(lines)
    REPORT_PATH.write_text(output, encoding="utf-8")
    return output
