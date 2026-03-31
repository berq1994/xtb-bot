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


def _decision_bucket(signal: dict) -> str:
    features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
    buy_decision = str(features.get("buy_decision") or "").strip().lower()
    category = str(signal.get("ticket", {}).get("category") or signal.get("supervisor", {}).get("reason") or "").strip().lower()
    decision = str(signal.get("decision") or signal.get("supervisor", {}).get("decision") or "").strip().lower()
    if buy_decision in {"buy_breakout", "buy_pullback", "buy_reversal"} or decision in {"long", "watch_long"}:
        return "buy_candidate"
    if buy_decision == "avoid":
        return "avoid"
    if category in {"winner_management", "drawdown_control", "portfolio_defense", "pullback_control"} or decision in {"reduce_risk", "watch_hedge"}:
        return "risk_management"
    return "watch"


def _is_quality_signal(signal: dict) -> bool:
    features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
    data_source = str(features.get("data_source") or "").lower()
    grade = str(features.get("evidence_grade") or "?")
    if "scaffold" in data_source or "fallback" in data_source:
        return False
    if grade in {"D", "?"}:
        return False
    return True


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def run_autonomous_learning_loop(limit: int = 120) -> str:
    history = _load_jsonl(HISTORY_PATH)
    outcomes = _load_jsonl(OUTCOME_PATH)
    if not history or not outcomes:
        output = "AUTONOMNÍ LEARNING LOOP\nMálo dat pro adaptivní stav."
        REPORT_PATH.write_text(output, encoding="utf-8")
        return output

    history_index = {_signal_id(row): row for row in history[-max(limit * 3, 120):]}
    resolved: list[tuple[dict, dict]] = []
    for row in outcomes[-max(limit * 3, 120):]:
        if row.get("outcome_label") not in {"win", "loss", "flat"}:
            continue
        signal = history_index.get(str(row.get("signal_id") or ""))
        if signal:
            resolved.append((signal, row))
    resolved = resolved[-limit:]

    by_bucket: dict[str, list[float]] = {}
    by_quality: dict[str, list[float]] = {"clean": [], "noisy": []}
    by_category: dict[str, list[float]] = {}
    by_grade: dict[str, list[float]] = {}
    by_playbook: dict[str, list[float]] = {}
    by_horizon: dict[str, list[float]] = {"h1d": [], "h3d": [], "h5d": [], "h20d": []}
    core_resolved: list[tuple[dict, dict]] = []

    for signal, outcome in resolved:
        features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
        result = float(outcome.get("outcome_pct", 0.0) or 0.0)
        bucket = _decision_bucket(signal)
        by_bucket.setdefault(bucket, []).append(result)
        by_quality["clean" if _is_quality_signal(signal) else "noisy"].append(result)
        category = str(signal.get("ticket", {}).get("category") or signal.get("supervisor", {}).get("reason") or "unknown")
        by_category.setdefault(category, []).append(result)
        grade = str(features.get("evidence_grade") or "?")
        by_grade.setdefault(grade, []).append(result)
        for key in ("h1d_pct", "h3d_pct", "h5d_pct", "h20d_pct"):
            if outcome.get(key) is not None:
                by_horizon[key.replace('_pct','')].append(float(outcome.get(key) or 0.0))
        for playbook in features.get("playbooks", []) or []:
            pid = str(playbook.get("id") if isinstance(playbook, dict) else playbook)
            if pid:
                by_playbook.setdefault(pid, []).append(result)
        if bucket == "buy_candidate" and _is_quality_signal(signal):
            core_resolved.append((signal, outcome))

    core_results = [float(out.get("outcome_pct", 0.0) or 0.0) for _, out in core_resolved]
    core_grade: dict[str, list[float]] = {}
    core_cat: dict[str, list[float]] = {}
    core_pb: dict[str, list[float]] = {}
    for signal, outcome in core_resolved:
        features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
        result = float(outcome.get("outcome_pct", 0.0) or 0.0)
        core_grade.setdefault(str(features.get("evidence_grade") or "?"), []).append(result)
        cat = str(signal.get("ticket", {}).get("category") or signal.get("supervisor", {}).get("reason") or "unknown")
        core_cat.setdefault(cat, []).append(result)
        for playbook in features.get("playbooks", []) or []:
            pid = str(playbook.get("id") if isinstance(playbook, dict) else playbook)
            if pid:
                core_pb.setdefault(pid, []).append(result)

    adaptive = {
        "weights_snapshot": load_signal_weights(),
        "sample_count": len(resolved),
        "core_sample_count": len(core_resolved),
        "bucket_avg": {k: round(mean(v), 2) for k, v in by_bucket.items() if v},
        "quality_avg": {k: round(mean(v), 2) for k, v in by_quality.items() if v},
        "category_avg": {k: round(mean(v), 2) for k, v in core_cat.items() if v},
        "evidence_grade_avg": {k: round(mean(v), 2) for k, v in core_grade.items() if v},
        "playbook_avg": {k: round(mean(v), 2) for k, v in core_pb.items() if v},
        "horizon_avg": {k: round(mean(v), 2) for k, v in by_horizon.items() if v},
    }

    thresholds = {
        "raise_priority_evidence_grade": None,
        "avoid_evidence_grade": None,
        "preferred_categories": [],
        "weak_playbooks": [],
        "learning_mode": "clean_buy_signals",
    }
    grade_avg = adaptive["evidence_grade_avg"]
    if grade_avg:
        thresholds["raise_priority_evidence_grade"] = max(grade_avg, key=grade_avg.get)
        thresholds["avoid_evidence_grade"] = min(grade_avg, key=grade_avg.get)
    thresholds["preferred_categories"] = [k for k, v in sorted(adaptive["category_avg"].items(), key=lambda kv: kv[1], reverse=True)[:3] if v > 0]
    thresholds["weak_playbooks"] = [k for k, v in adaptive["playbook_avg"].items() if v < 0]
    adaptive["thresholds"] = thresholds

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(adaptive, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "AUTONOMNÍ LEARNING LOOP",
        f"Vyhodnocené vzorky celkem: {len(resolved)}",
        f"Čisté buy vzorky pro učení: {len(core_resolved)}",
        f"Bucket buy_candidate avg: {_avg(by_bucket.get('buy_candidate', [])) if by_bucket.get('buy_candidate') else '-'}",
        f"Bucket risk_management avg: {_avg(by_bucket.get('risk_management', [])) if by_bucket.get('risk_management') else '-'}",
        f"Bucket avoid avg: {_avg(by_bucket.get('avoid', [])) if by_bucket.get('avoid') else '-'}",
        f"Kvalita clean avg: {_avg(by_quality.get('clean', [])) if by_quality.get('clean') else '-'}",
        f"Kvalita noisy avg: {_avg(by_quality.get('noisy', [])) if by_quality.get('noisy') else '-'}",
        f"Preferované kategorie: {', '.join(thresholds['preferred_categories']) if thresholds['preferred_categories'] else 'žádné'}",
        f"Nejlepší evidence grade: {thresholds['raise_priority_evidence_grade'] or '-'}",
        f"Slabý evidence grade: {thresholds['avoid_evidence_grade'] or '-'}",
        f"Slabé playbooky: {', '.join(thresholds['weak_playbooks']) if thresholds['weak_playbooks'] else 'žádné'}",
    ]
    output = "\n".join(lines)
    REPORT_PATH.write_text(output, encoding="utf-8")
    return output
