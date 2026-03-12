from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from agents.signal_history_agent import HISTORY_PATH

OUTCOME_PATH = Path("data/outcome_tracking.jsonl")
REVIEW_PATH = Path("data/outcome_review.txt")
EXAMPLE_PATH = Path("production/outcome_update_example.txt")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def run_outcome_update() -> str:
    history = _load_jsonl(HISTORY_PATH)
    OUTCOME_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not history:
        output = "\n".join([
            "OUTCOME UPDATE",
            "Status: no_history",
            "Reason: log_signal/full_cycle has not created any history yet",
        ])
        EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EXAMPLE_PATH.write_text(
            "Add real results later in data/outcome_tracking.jsonl with fields: "
            "timestamp, symbol, decision, outcome_pct, outcome_label",
            encoding="utf-8",
        )
        return output

    latest = history[-1]
    ticket = latest.get("ticket", {})
    row = {
        "timestamp": latest.get("timestamp"),
        "symbol": ticket.get("symbol", "NONE"),
        "decision": latest.get("supervisor", {}).get("decision", "wait"),
        "outcome_pct": 0.0,
        "outcome_label": "pending",
    }
    with OUTCOME_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    output = "\n".join([
        "OUTCOME UPDATE",
        f"Symbol: {row['symbol']}",
        f"Decision: {row['decision']}",
        "Status: placeholder outcome row added",
        f"File: {OUTCOME_PATH.as_posix()}",
    ])
    EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE_PATH.write_text(output, encoding="utf-8")
    return output


def run_outcome_review() -> str:
    rows = _load_jsonl(OUTCOME_PATH)
    if not rows:
        output = "\n".join([
            "OUTCOME REVIEW",
            "Samples: 0",
            "Average outcome %: 0.0",
        ])
        REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        REVIEW_PATH.write_text(output, encoding="utf-8")
        return output

    vals = [float(r.get("outcome_pct", 0.0)) for r in rows]
    labels: dict[str, int] = {}
    for row in rows:
        lbl = row.get("outcome_label", "pending")
        labels[lbl] = labels.get(lbl, 0) + 1

    lines = [
        "OUTCOME REVIEW",
        f"Samples: {len(rows)}",
        f"Average outcome %: {round(mean(vals), 3)}",
        "Labels:",
    ]
    for key, value in labels.items():
        lines.append(f"- {key}: {value}")

    output = "\n".join(lines)
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text(output, encoding="utf-8")
    return output
