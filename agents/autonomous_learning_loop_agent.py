from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from agents.learning_agent import load_signal_weights

HISTORY_PATH = Path("data/openbb_signal_history.jsonl")
OUTCOME_PATH = Path("data/outcome_tracking.jsonl")
STATE_PATH = Path("data/autonomous_learning_state.json")
REPORT_PATH = Path("autonomous_learning_report.txt")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _signal_id(row: dict) -> str:
    return str(row.get("signal_id") or f"{row.get('timestamp', '')}|{row.get('ticket_symbol') or row.get('ticket', {}).get('symbol') or 'NONE'}")


def run_autonomous_learning_loop(limit: int = 120) -> str:
    history = _load_jsonl(HISTORY_PATH)
    outcomes = _load_jsonl(OUTCOME_PATH)
    if not history or not outcomes:
        output = "AUTONOMNÍ LEARNING LOOP\nMálo dat pro adaptivní stav."
        REPORT_PATH.write_text(output, encoding="utf-8")
        return output

    history_index = {_signal_id(row): row for row in history[-max(limit * 2, 80):]}
    resolved = []
    for row in outcomes[-max(limit * 2, 80):]:
        if row.get("outcome_label") not in {"win", "loss", "flat"}:
            continue
        signal = history_index.get(str(row.get("signal_id") or ""))
        if signal:
            resolved.append((signal, row))
    resolved = resolved[-limit:]

    by_category: dict[str, list[float]] = {}
    by_grade: dict[str, list[float]] = {}
    by_playbook: dict[str, list[float]] = {}
    by_study_strength: dict[str, list[float]] = {"high": [], "low": []}
    for signal, outcome in resolved:
        features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
        result = float(outcome.get("outcome_pct", 0.0) or 0.0)
        category = str(signal.get("ticket", {}).get("category") or signal.get("supervisor", {}).get("reason") or "unknown")
        by_category.setdefault(category, []).append(result)
        grade = str(features.get("evidence_grade") or "?")
        by_grade.setdefault(grade, []).append(result)
        study_score = float(features.get("study_alignment_score", 0.0) or 0.0)
        by_study_strength["high" if study_score >= 0.65 else "low"].append(result)
        for playbook in features.get("playbooks", []) or []:
            pid = str(playbook.get("id") if isinstance(playbook, dict) else playbook)
            if pid:
                by_playbook.setdefault(pid, []).append(result)

    adaptive = {
        "weights_snapshot": load_signal_weights(),
        "sample_count": len(resolved),
        "category_avg": {k: round(mean(v), 2) for k, v in by_category.items() if v},
        "evidence_grade_avg": {k: round(mean(v), 2) for k, v in by_grade.items() if v},
        "playbook_avg": {k: round(mean(v), 2) for k, v in by_playbook.items() if v},
        "study_alignment_avg": {k: round(mean(v), 2) for k, v in by_study_strength.items() if v},
    }

    thresholds = {
        "raise_priority_evidence_grade": None,
        "avoid_evidence_grade": None,
        "preferred_categories": [],
        "weak_playbooks": [],
    }
    grade_avg = adaptive["evidence_grade_avg"]
    if grade_avg:
        best_grade = max(grade_avg, key=grade_avg.get)
        worst_grade = min(grade_avg, key=grade_avg.get)
        thresholds["raise_priority_evidence_grade"] = best_grade
        thresholds["avoid_evidence_grade"] = worst_grade
    cat_avg = adaptive["category_avg"]
    thresholds["preferred_categories"] = [k for k, v in sorted(cat_avg.items(), key=lambda kv: kv[1], reverse=True)[:3] if v > 0]
    pb_avg = adaptive["playbook_avg"]
    thresholds["weak_playbooks"] = [k for k, v in pb_avg.items() if v < 0]
    adaptive["thresholds"] = thresholds

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(adaptive, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "AUTONOMNÍ LEARNING LOOP",
        f"Vyhodnocené vzorky: {len(resolved)}",
        f"Preferované kategorie: {', '.join(thresholds['preferred_categories']) if thresholds['preferred_categories'] else 'žádné'}",
        f"Nejlepší evidence grade: {thresholds['raise_priority_evidence_grade'] or '-'}",
        f"Slabý evidence grade: {thresholds['avoid_evidence_grade'] or '-'}",
        f"Slabé playbooky: {', '.join(thresholds['weak_playbooks']) if thresholds['weak_playbooks'] else 'žádné'}",
    ]
    output = "\n".join(lines)
    REPORT_PATH.write_text(output, encoding="utf-8")
    return output
