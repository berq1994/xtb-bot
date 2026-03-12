from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from agents.signal_history_agent import HISTORY_PATH
from cz_utils import decision_cs, status_cs

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
        output = "\n".join(sections).strip()".join([
            "AKTUALIZACE VĂťSLEDKU",
            f"Stav: {status_cs('no_history')}",
            "DĹŻvod: log_signal/full_cycle zatĂ­m nevytvoĹ™il ĹľĂˇdnou historii",
        ])
        EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EXAMPLE_PATH.write_text(
            "PozdÄ›ji doplĹ reĂˇlnĂ© vĂ˝sledky do data/outcome_tracking.jsonl s poli: "
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
        fh.write(json.dumps(row, ensure_ascii=False) + "
")

    output = "\n".join(sections).strip()".join([
        "AKTUALIZACE VĂťSLEDKU",
        f"Symbol: {row['symbol']}",
        f"RozhodnutĂ­: {decision_cs(row['decision'])}",
        "Stav: pĹ™idĂˇn zĂˇznam placeholderu vĂ˝sledku",
        f"Soubor: {OUTCOME_PATH.as_posix()}",
    ])
    EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE_PATH.write_text(output, encoding="utf-8")
    return output


def run_outcome_review() -> str:
    rows = _load_jsonl(OUTCOME_PATH)
    if not rows:
        output = "\n".join(sections).strip()".join([
            "PĹEHLED VĂťSLEDKĹ®",
            "PoÄŤet vzorkĹŻ: 0",
            "PrĹŻmÄ›rnĂ˝ vĂ˝sledek %: 0.0",
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
        "PĹEHLED VĂťSLEDKĹ®",
        f"PoÄŤet vzorkĹŻ: {len(rows)}",
        f"PrĹŻmÄ›rnĂ˝ vĂ˝sledek %: {round(mean(vals), 3)}",
        "Ĺ tĂ­tky:",
    ]
    for key, value in labels.items():
        lines.append(f"- {status_cs(key)}: {value}")

    output = "\n".join(sections).strip()".join(lines)
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text(output, encoding="utf-8")
    return output


