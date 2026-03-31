from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from agents.learning_agent import load_signal_weights

RESEARCH_STATE_PATH = Path("data/research_live_state.json")
FUNDAMENTALS_STATE_PATH = Path("data/fundamentals_state.json")
HISTORY_PATH = Path("data/openbb_signal_history.jsonl")
OUTCOME_PATH = Path("data/outcome_tracking.jsonl")
STATE_PATH = Path("data/autonomous_learning_state.json")
REPORT_PATH = Path("autonomous_learning_report.txt")




def _load_latest_research_index() -> dict[str, dict]:
    if not RESEARCH_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(RESEARCH_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = []
    if isinstance(payload, dict):
        for key in ("top_items", "all_items"):
            value = payload.get(key, [])
            if isinstance(value, list):
                rows.extend([r for r in value if isinstance(r, dict)])
    index: dict[str, dict] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol and symbol not in index:
            index[symbol] = row
    return index


def _merge_missing_signal_context(signal: dict, latest_index: dict[str, dict], fundamentals_index: dict[str, dict] | None = None) -> dict:
    if not isinstance(signal, dict):
        return {}
    symbol = str(signal.get("ticket_symbol") or signal.get("ticket", {}).get("symbol") or "").strip().upper()
    latest = latest_index.get(symbol) if symbol else None
    fundamentals_row = (fundamentals_index or {}).get(symbol) if symbol else None
    if not latest and not fundamentals_row:
        return signal
    merged = dict(signal)
    if latest:
        top_defaults = {
            "source": latest.get("source"),
            "quality_class": latest.get("quality_class"),
            "official_item_count": latest.get("official_item_count"),
            "fundamental_provider": latest.get("fundamental_provider"),
            "fundamental_score": latest.get("fundamental_score"),
            "fundamental_bias": latest.get("fundamental_bias"),
            "data_quality_score": latest.get("data_quality_score"),
            "buy_decision": latest.get("buy_decision"),
            "technical_setup": latest.get("technical_setup"),
            "ta_score": latest.get("ta_score"),
        }
        for key, value in top_defaults.items():
            merged[key] = _merge_prefer(merged.get(key), value, key)
        if isinstance(latest.get("fundamentals"), dict):
            current_fundamentals = merged.get("fundamentals") if isinstance(merged.get("fundamentals"), dict) else {}
            if not current_fundamentals or str(current_fundamentals.get("provider", "")).strip().lower() == "fallback":
                merged["fundamentals"] = latest.get("fundamentals")
    if fundamentals_row:
        merged["fundamental_provider"] = _merge_prefer(merged.get("fundamental_provider"), fundamentals_row.get("status"), "fundamental_provider")
        merged["fundamental_score"] = _merge_prefer(merged.get("fundamental_score"), fundamentals_row.get("fundamental_score"), "fundamental_score")
        merged["fundamental_bias"] = _merge_prefer(merged.get("fundamental_bias"), fundamentals_row.get("fundamental_bias"), "fundamental_bias")
        current_fundamentals = merged.get("fundamentals") if isinstance(merged.get("fundamentals"), dict) else {}
        if not current_fundamentals or str(current_fundamentals.get("provider", "")).strip().lower() == "fallback":
            merged["fundamentals"] = dict(fundamentals_row)
    features = dict(merged.get("features") or {})
    feature_defaults = {}
    if latest:
        feature_defaults.update({
            "quality_class": latest.get("quality_class"),
            "data_quality_score": latest.get("data_quality_score"),
            "evidence_grade": latest.get("evidence_grade"),
            "evidence_score": latest.get("evidence_score"),
            "official_item_count": latest.get("official_item_count"),
            "fundamental_provider": latest.get("fundamental_provider"),
            "fundamental_score": latest.get("fundamental_score"),
            "fundamental_bias": latest.get("fundamental_bias"),
            "buy_decision": latest.get("buy_decision"),
            "technical_setup": latest.get("technical_setup"),
            "ta_score": latest.get("ta_score"),
            "source": latest.get("source"),
            "data_source": latest.get("source"),
            "news_providers": latest.get("news_providers", []),
            "playbooks": latest.get("playbooks", []),
            "study_alignment_score": latest.get("study_alignment_score"),
            "matched_studies": latest.get("matched_studies", []),
            "trend": latest.get("trend"),
            "momentum_5d": latest.get("momentum_5d"),
            "momentum_20d": latest.get("momentum_20d"),
            "theme_overlap_penalty": latest.get("theme_overlap_penalty"),
            "held": latest.get("held"),
            "pnl_vs_cost_pct": latest.get("pnl_vs_cost_pct"),
            "category": latest.get("category"),
            "priority_score": latest.get("priority_score"),
            "actionability_score": latest.get("actionability_score"),
            "action_bucket": latest.get("action_bucket"),
            "urgency_label": latest.get("urgency_label"),
            "thesis_strength": latest.get("thesis_strength"),
            "clean_long_score": latest.get("clean_long_score"),
        })
    if fundamentals_row:
        feature_defaults.update({
            "fundamental_provider": fundamentals_row.get("status"),
            "fundamental_score": fundamentals_row.get("fundamental_score"),
            "fundamental_bias": fundamentals_row.get("fundamental_bias"),
        })
    for key, value in feature_defaults.items():
        features[key] = _merge_prefer(features.get(key), value, key)
    merged["features"] = features
    return merged



def _load_fundamentals_index() -> dict[str, dict]:
    if not FUNDAMENTALS_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(FUNDAMENTALS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, dict] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            symbol = str(value.get("symbol") or key or "").strip().upper()
            if symbol:
                out[symbol] = value
    return out


def _is_emptyish(value) -> bool:
    return value in (None, "", [], {})


def _evidence_rank(value: str) -> int:
    grades = {"A": 4, "B": 3, "C": 2, "D": 1, "?": 0, "": 0}
    return grades.get(str(value or "").strip().upper(), 0)


def _quality_rank(value: str) -> int:
    mapping = {"": 0, "blocked": 0, "noisy": 1, "clean": 2}
    return mapping.get(str(value or "").strip().lower(), 0)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return default


def _long_support_score(signal: dict) -> float:
    features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
    trend = str(features.get("trend") or signal.get("trend") or "").strip().lower()
    m5 = _safe_float(features.get("momentum_5d") or signal.get("momentum_5d"))
    m20 = _safe_float(features.get("momentum_20d") or signal.get("momentum_20d"))
    pnl = _safe_float(features.get("pnl_vs_cost_pct") or signal.get("pnl_vs_cost_pct"))
    overlap = _safe_float(features.get("theme_overlap_penalty") or signal.get("theme_overlap_penalty"))
    held = bool(features.get("held") if features.get("held") is not None else signal.get("held"))
    category = str(features.get("category") or signal.get("category") or signal.get("ticket", {}).get("category") or signal.get("supervisor", {}).get("reason") or "").strip().lower()
    ta_score = _safe_float(features.get("ta_score") or signal.get("ta_score"))
    ta_setup = str(features.get("technical_setup") or signal.get("technical_setup") or "").strip().lower()
    ta_decision = str(features.get("buy_decision") or signal.get("buy_decision") or "").strip().lower()
    official_count = int(features.get("official_item_count") or signal.get("official_item_count") or 0)
    fundamental_score = _safe_float(features.get("fundamental_score") or signal.get("fundamental_score") or signal.get("fundamentals", {}).get("fundamental_score"))
    fundamental_bias = str(features.get("fundamental_bias") or signal.get("fundamental_bias") or signal.get("fundamentals", {}).get("fundamental_bias") or "").strip().lower()
    evidence_grade = str(features.get("evidence_grade") or "").strip().upper()
    evidence_score = _safe_float(features.get("evidence_score"))
    score = 0.0
    if trend == "up": score += 0.35
    elif trend == "flat": score += 0.1
    if m5 > 0: score += 0.2
    if m5 >= 2: score += 0.1
    if m20 > 0: score += 0.2
    if m20 >= 4: score += 0.1
    if held and pnl > 0: score += 0.2
    if overlap <= 0.15: score += 0.1
    if category in {"winner_management", "breakout_watch", "pullback_control"}: score += 0.15
    if ta_score >= 2.0: score += 0.15
    if ta_decision not in {"avoid", "defensive_only"}: score += 0.1
    if ta_setup not in {"breakdown"}: score += 0.05
    if official_count > 0: score += 0.25
    if fundamental_score >= 0.2 or fundamental_bias in {"positive", "bullish"}: score += 0.25
    if evidence_grade in {"A", "B", "C"}: score += 0.2
    elif evidence_score >= 0.2: score += 0.1
    return round(score, 2)



def _clean_long_score(signal: dict) -> float:
    features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
    trend = str(features.get("trend") or signal.get("trend") or "").strip().lower()
    m5 = _safe_float(features.get("momentum_5d") or signal.get("momentum_5d"))
    m20 = _safe_float(features.get("momentum_20d") or signal.get("momentum_20d"))
    overlap = _safe_float(features.get("theme_overlap_penalty") or signal.get("theme_overlap_penalty"))
    held = bool(features.get("held") if features.get("held") is not None else signal.get("held"))
    pnl = _safe_float(features.get("pnl_vs_cost_pct") or signal.get("pnl_vs_cost_pct"))
    category = str(features.get("category") or signal.get("category") or signal.get("ticket", {}).get("category") or signal.get("supervisor", {}).get("reason") or "").strip().lower()
    ta_score = _safe_float(features.get("ta_score") or signal.get("ta_score"))
    ta_setup = str(features.get("technical_setup") or signal.get("technical_setup") or "").strip().lower()
    ta_decision = str(features.get("buy_decision") or signal.get("buy_decision") or "").strip().lower()
    official_count = int(features.get("official_item_count") or signal.get("official_item_count") or 0)
    fundamental_score = _safe_float(features.get("fundamental_score") or signal.get("fundamental_score") or signal.get("fundamentals", {}).get("fundamental_score"))
    fundamental_bias = str(features.get("fundamental_bias") or signal.get("fundamental_bias") or signal.get("fundamentals", {}).get("fundamental_bias") or "").strip().lower()
    evidence_grade = str(features.get("evidence_grade") or "").strip().upper()
    evidence_score = _safe_float(features.get("evidence_score"))
    data_quality = _safe_float(features.get("data_quality_score") or signal.get("data_quality_score"))
    study_alignment = _safe_float(features.get("study_alignment_score"))
    playbooks = features.get("playbooks") or []
    score = 0.0
    if trend == 'up': score += 0.3
    elif trend == 'flat': score += 0.08
    if m5 > 0: score += 0.12
    if m5 >= 2.0: score += 0.08
    if m20 > 0: score += 0.12
    if m20 >= 4.0: score += 0.08
    if overlap <= 0.15: score += 0.1
    elif overlap <= 0.25: score += 0.05
    if ta_score >= 2.0: score += 0.12
    if ta_score >= 3.5: score += 0.12
    if ta_setup in {'pullback', 'breakout', 'range'}: score += 0.08
    elif ta_setup not in {'', 'none', 'unknown', 'breakdown'}: score += 0.04
    if ta_decision in {'buy_breakout', 'buy_pullback', 'buy_reversal'}: score += 0.18
    elif ta_decision not in {'avoid', 'defensive_only'}: score += 0.05
    if official_count > 0: score += 0.18
    if fundamental_score >= 0.2 or fundamental_bias in {'positive', 'bullish'}: score += 0.18
    if fundamental_score >= 0.45: score += 0.1
    if data_quality >= 0.6: score += 0.08
    if data_quality >= 0.75: score += 0.08
    if evidence_grade in {'A', 'B'}: score += 0.18
    elif evidence_grade == 'C': score += 0.12
    elif evidence_score >= 0.45: score += 0.06
    if study_alignment >= 0.6: score += 0.08
    if playbooks: score += 0.05
    if held and pnl > 0: score += 0.05
    if category in {'winner_management', 'breakout_watch', 'pullback_control'}: score += 0.06
    return round(score, 2)


def _is_weak_value(key: str, value) -> bool:
    if _is_emptyish(value):
        return True
    if key in {"source", "data_source", "news_source"}:
        text = str(value).strip().lower()
        return (not text) or ("scaffold" in text) or ("fallback" in text)
    if key == "quality_class":
        return str(value).strip().lower() in {"", "blocked", "noisy"}
    if key == "official_item_count":
        return int(value or 0) <= 0
    if key == "fundamental_provider":
        text = str(value).strip().lower()
        return (not text) or text == "fallback"
    if key == "fundamental_score":
        return abs(float(value or 0.0)) < 0.05
    if key == "fundamental_bias":
        return str(value).strip().lower() in {"", "neutral"}
    if key == "data_quality_score":
        return float(value or 0.0) < 0.55
    if key == "evidence_grade":
        return _evidence_rank(str(value)) <= 1
    if key == "evidence_score":
        return float(value or 0.0) < 0.35
    if key == "buy_decision":
        return str(value).strip().lower() in {"", "watch", "avoid"}
    if key == "technical_setup":
        return str(value).strip().lower() in {"", "none", "unknown"}
    if key == "ta_score":
        return float(value or 0.0) < 1.0
    if key == "study_alignment_score":
        return float(value or 0.0) < 0.55
    if key == "news_providers":
        vals = [str(v).lower() for v in (value or [])]
        return not vals or all(("scaffold" in v) or ("fallback" in v) for v in vals)
    if key == "playbooks":
        return not bool(value)
    return False


def _merge_prefer(current, latest, key: str):
    if key == 'quality_class':
        return latest if _quality_rank(latest) > _quality_rank(current) else current
    if key == 'evidence_grade':
        return latest if _evidence_rank(latest) > _evidence_rank(current) else current
    if _is_weak_value(key, current) and not _is_weak_value(key, latest):
        return latest
    return current

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


def _signal_quality(signal: dict) -> str:
    features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
    data_source = str(features.get("data_source") or features.get("source") or signal.get('source') or "").lower()
    grade = str(features.get("evidence_grade") or "?").upper()
    dq = float(features.get('data_quality_score', signal.get('data_quality_score', 0.0)) or 0.0)
    official_count = int(features.get('official_item_count', signal.get('official_item_count', 0)) or 0)
    fundamental_provider = str(
        signal.get('fundamental_provider')
        or features.get('fundamental_provider')
        or signal.get('fundamentals', {}).get('provider', '')
        or ''
    ).strip().lower()
    fundamental_score = float(
        signal.get('fundamental_score')
        or features.get('fundamental_score')
        or signal.get('fundamentals', {}).get('fundamental_score', 0.0)
        or 0.0
    )
    quality_class = str(signal.get('quality_class') or features.get('quality_class') or '').strip().lower()
    bucket = _decision_bucket(signal)
    has_scaffold = 'scaffold' in data_source
    has_fallback = 'fallback' in data_source
    has_live_fundamental = bool(fundamental_provider and fundamental_provider != 'fallback')
    fundamental_bias = str(
        signal.get('fundamental_bias')
        or features.get('fundamental_bias')
        or signal.get('fundamentals', {}).get('fundamental_bias', '')
        or ''
    ).strip().lower()
    has_strong_context = official_count > 0 or has_live_fundamental or abs(fundamental_score) >= 0.25
    ta_setup = str(features.get("technical_setup") or signal.get("technical_setup") or "").strip().lower()
    ta_decision = str(features.get("buy_decision") or signal.get("buy_decision") or "").strip().lower()
    ta_score = float(features.get("ta_score", signal.get("ta_score", 0.0)) or 0.0)
    supportive_ta = ta_decision not in {"avoid", "defensive_only"} and ta_setup not in {"breakdown", "none"}
    weak_ta_but_fundamental = ta_decision in {"watch", ""} and ta_setup in {"none", "range", "pullback"}
    positive_fundamental = has_live_fundamental and (fundamental_score >= 0.15 or fundamental_bias in {'positive', 'bullish'})
    official_supported = official_count > 0
    clean_long_score = max(_clean_long_score(signal), _safe_float(features.get('clean_long_score')))
    supportive_evidence = grade in {'A', 'B', 'C'} or _safe_float(features.get('evidence_score')) >= 0.45 or official_count > 0
    long_support_score = _long_support_score(signal)
    legacy_long_ok = long_support_score >= 1.05 and dq >= 0.45 and ta_decision != 'avoid' and ta_setup != 'breakdown'
    medium_clean_context = (
        bucket == 'buy_candidate'
        and clean_long_score >= 0.9
        and dq >= 0.5
        and ta_decision not in {'avoid', 'defensive_only'}
        and ta_setup != 'breakdown'
        and (
            (positive_fundamental and (official_supported or ta_score >= 1.5 or supportive_ta))
            or (official_supported and ta_score >= 1.4)
            or (supportive_evidence and positive_fundamental and ta_score >= 1.5)
            or (has_strong_context and supportive_ta and clean_long_score >= 1.0)
        )
    )
    promoted_clean_long = medium_clean_context or (clean_long_score >= 1.1 and dq >= 0.58 and ta_decision not in {'avoid', 'defensive_only'} and ta_setup != 'breakdown' and (positive_fundamental or supportive_ta or official_supported))
    long_recovery_context = supportive_ta and (
        positive_fundamental
        or (official_supported and dq >= 0.45 and ta_score >= 1.0)
        or (has_live_fundamental and dq >= 0.45 and ta_score >= 1.25 and fundamental_score >= 0.1)
        or (grade in {'A', 'B', 'C'} and dq >= 0.5 and not has_scaffold)
        or (weak_ta_but_fundamental and positive_fundamental and dq >= 0.45)
    )
    if quality_class == 'clean':
        return 'clean'
    if not has_scaffold and not has_fallback and grade in {"A", "B"} and dq >= 0.7:
        return 'clean'
    if grade == 'C' and dq >= 0.65 and (not has_scaffold or has_strong_context):
        return 'clean'
    if bucket == 'buy_candidate' and ((clean_long_score >= 1.1 and dq >= 0.58 and ta_decision not in {'avoid', 'defensive_only'} and ta_setup != 'breakdown' and (positive_fundamental or supportive_evidence or has_strong_context)) or medium_clean_context):
        return 'clean'
    if quality_class == 'noisy':
        return 'noisy'
    if bucket == 'buy_candidate':
        if promoted_clean_long:
            return 'clean'
        if dq >= 0.58 and (grade in {'A', 'B', 'C'} or has_strong_context):
            return 'noisy'
        if dq >= 0.45 and positive_fundamental and (grade in {'C', 'D', '?'} or has_strong_context) and ta_decision != 'avoid':
            return 'noisy'
        if dq >= 0.5 and has_strong_context and (supportive_ta or weak_ta_but_fundamental):
            return 'noisy'
        if long_recovery_context or legacy_long_ok:
            return 'noisy'
        if has_live_fundamental and positive_fundamental and dq >= 0.4 and ta_score >= 1.1 and ta_decision != 'avoid':
            return 'noisy'
        return 'reject'
    if bucket == 'risk_management':
        if dq >= 0.4 or has_strong_context:
            return 'noisy'
        return 'reject'
    if bucket == 'watch':
        if dq >= 0.5 and (grade in {'A', 'B', 'C'} or has_strong_context or not has_scaffold):
            return 'noisy'
        if dq >= 0.45 and positive_fundamental and (grade in {'C', 'D', '?'} or has_strong_context) and ta_decision != 'avoid':
            return 'noisy'
        if dq >= 0.45 and has_strong_context and supportive_ta:
            return 'noisy'
        if dq >= 0.4 and has_live_fundamental and ta_score >= 1.5 and ta_decision != 'avoid':
            return 'noisy'
        if long_recovery_context or legacy_long_ok:
            return 'noisy'
        return 'reject'
    return 'reject'


def _is_quality_signal(signal: dict) -> bool:
    return _signal_quality(signal) == 'clean'


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def run_autonomous_learning_loop(limit: int = 120) -> str:
    history = _load_jsonl(HISTORY_PATH)
    outcomes = _load_jsonl(OUTCOME_PATH)
    if not history or not outcomes:
        output = "AUTONOMNÍ LEARNING LOOP\nMálo dat pro adaptivní stav."
        REPORT_PATH.write_text(output, encoding="utf-8")
        return output

    latest_research_index = _load_latest_research_index()
    fundamentals_index = _load_fundamentals_index()
    history_index = {_signal_id(row): _merge_missing_signal_context(row, latest_research_index, fundamentals_index) for row in history[-max(limit * 3, 120):]}
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

    learnable_resolved: list[tuple[dict, dict]] = []
    for signal, outcome in resolved:
        features = signal.get("features", {}) if isinstance(signal.get("features"), dict) else {}
        result = float(outcome.get("outcome_pct", 0.0) or 0.0)
        bucket = _decision_bucket(signal)
        quality = _signal_quality(signal)
        by_bucket.setdefault(bucket, []).append(result)
        if quality in by_quality:
            by_quality[quality].append(result)
        if bucket in {'buy_candidate', 'watch', 'risk_management'} and quality != 'reject':
            learnable_resolved.append((signal, outcome))
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
        if bucket == "buy_candidate" and quality == 'clean':
            core_resolved.append((signal, outcome))

    if not core_resolved:
        for signal, outcome in learnable_resolved:
            if _decision_bucket(signal) in {'buy_candidate', 'risk_management'}:
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
        f"Čisté buy vzorky pro učení: {sum(1 for s, _ in core_resolved if _signal_quality(s) == 'clean')}",
        f"Fallback učící vzorky: {sum(1 for s, _ in core_resolved if _signal_quality(s) != 'clean')}",
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
