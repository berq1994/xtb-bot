
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

RESEARCH_STATE_PATH = Path("data/research_live_state.json")
HISTORY_PATH = Path("data/openbb_signal_history.jsonl")
OUTCOME_PATH = Path("data/outcome_tracking.jsonl")
WEIGHTS_PATH = Path("data/phase5_signal_weights.json")
USER_FEEDBACK_PATH = Path("data/user_feedback.jsonl")

DEFAULT_WEIGHTS = {
    "trend": 1.0,
    "momentum": 1.0,
    "sentiment": 1.0,
    "regime_alignment": 1.0,
    "risk_penalty": 1.0,
    "evidence_quality": 1.0,
    "playbook_alignment": 1.0,
    "study_alignment": 1.0,
}


def _load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows




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


def _merge_missing_signal_context(signal: dict, latest_index: dict[str, dict]) -> dict:
    if not isinstance(signal, dict):
        return {}
    symbol = str(signal.get("ticket_symbol") or signal.get("ticket", {}).get("symbol") or "").strip().upper()
    latest = latest_index.get(symbol) if symbol else None
    if not latest:
        return signal
    merged = dict(signal)
    merged.setdefault("source", latest.get("source"))
    merged.setdefault("quality_class", latest.get("quality_class"))
    merged.setdefault("official_item_count", latest.get("official_item_count"))
    merged.setdefault("fundamental_provider", latest.get("fundamental_provider"))
    merged.setdefault("fundamental_score", latest.get("fundamental_score"))
    merged.setdefault("fundamental_bias", latest.get("fundamental_bias"))
    merged.setdefault("data_quality_score", latest.get("data_quality_score"))
    if isinstance(latest.get("fundamentals"), dict) and not isinstance(merged.get("fundamentals"), dict):
        merged["fundamentals"] = latest.get("fundamentals")
    features = dict(merged.get("features") or {})
    feature_defaults = {
        "quality_class": latest.get("quality_class"),
        "data_quality_score": latest.get("data_quality_score"),
        "evidence_grade": latest.get("evidence_grade"),
        "evidence_score": latest.get("evidence_score"),
        "official_item_count": latest.get("official_item_count"),
        "fundamental_provider": latest.get("fundamental_provider"),
        "fundamental_score": latest.get("fundamental_score"),
        "buy_decision": latest.get("buy_decision"),
        "technical_setup": latest.get("technical_setup"),
        "ta_score": latest.get("ta_score"),
        "source": latest.get("source"),
        "data_source": latest.get("source"),
        "news_providers": latest.get("news_providers", []),
        "playbooks": latest.get("playbooks", []),
        "study_alignment_score": latest.get("study_alignment_score"),
        "matched_studies": latest.get("matched_studies", []),
    }
    for key, value in feature_defaults.items():
        current = features.get(key)
        if current in (None, "", [], {}):
            if value not in (None, "", [], {}):
                features[key] = value
    merged["features"] = features
    return merged

def load_signal_weights() -> dict:
    if not WEIGHTS_PATH.exists():
        return DEFAULT_WEIGHTS.copy()
    try:
        data = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = DEFAULT_WEIGHTS.copy()
            merged.update({k: float(v) for k, v in data.items() if k in DEFAULT_WEIGHTS})
            return merged
    except Exception:
        pass
    return DEFAULT_WEIGHTS.copy()


def _save_weights(weights: dict) -> None:
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_PATH.write_text(json.dumps(weights, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_history_index(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        signal_id = str(row.get("signal_id") or f"{row.get('timestamp', '')}|{row.get('ticket_symbol') or row.get('ticket', {}).get('symbol') or 'NONE'}")
        out[signal_id] = row
    return out


def _feedback_bias() -> dict[str, float]:
    rows = _load_rows(USER_FEEDBACK_PATH)[-100:]
    if not rows:
        return {}
    useful_vals = [float(r.get("usefulness", 0.0)) for r in rows if r.get("usefulness") is not None]
    if not useful_vals:
        return {}
    avg_usefulness = mean(useful_vals)
    return {"overall_feedback_avg": round(avg_usefulness, 2)}


def _decision_bucket(decision: str) -> str:
    value = str(decision or '').strip().lower()
    if any(tag in value for tag in ['avoid', 'defensive_only']):
        return 'avoid'
    if any(tag in value for tag in ['drawdown', 'portfolio_defense', 'winner_management', 'trim', 'hedge', 'pullback_control']):
        return 'risk_management'
    if any(tag in value for tag in ['buy', 'long']):
        return 'buy_candidate'
    if 'watch' in value:
        return 'watch_candidate'
    return 'other'


def _row_quality(signal: dict, outcome: dict) -> str:
    decision = str(outcome.get('decision') or signal.get('decision') or '')
    bucket = _decision_bucket(decision)
    if bucket not in {'buy_candidate', 'watch_candidate', 'risk_management'}:
        return 'reject'

    features = signal.get('features', {}) if isinstance(signal, dict) else {}
    quality_class = str(
        signal.get('quality_class')
        or features.get('quality_class')
        or signal.get('quality_label')
        or ''
    ).strip().lower()
    weak_source = str(
        features.get('news_source')
        or features.get('source')
        or features.get('data_source')
        or signal.get('source')
        or ''
    ).strip().lower()
    grade = str(features.get('evidence_grade', '?')).strip().upper()
    dq = float(features.get('data_quality_score', signal.get('data_quality_score', 0.0)) or 0.0)
    official_count = int(
        features.get('official_item_count', signal.get('official_item_count', 0) or 0) or 0
    )
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
    has_scaffold = 'scaffold' in weak_source
    has_fallback = 'fallback' in weak_source
    has_live_fundamental = bool(fundamental_provider and fundamental_provider != 'fallback')
    has_strong_context = official_count > 0 or has_live_fundamental or abs(fundamental_score) >= 0.25

    if quality_class == 'clean':
        return 'clean'
    if quality_class == 'noisy' and bucket in {'buy_candidate', 'watch_candidate', 'risk_management'}:
        return 'noisy'

    if grade in {'A', 'B'} and not has_scaffold and dq >= 0.7:
        return 'clean'
    if grade == 'C' and dq >= 0.65 and (not has_scaffold or has_strong_context):
        return 'clean'

    if not features:
        if bucket in {'buy_candidate', 'watch_candidate', 'risk_management'}:
            return 'noisy'
        return 'reject'

    ta_setup = str(features.get("technical_setup") or signal.get("technical_setup") or "").strip().lower()
    ta_decision = str(features.get("buy_decision") or signal.get("buy_decision") or "").strip().lower()
    ta_score = float(features.get("ta_score", signal.get("ta_score", 0.0)) or 0.0)
    supportive_ta = ta_decision not in {"avoid", "defensive_only"} and ta_setup not in {"breakdown"}

    if bucket == 'buy_candidate':
        if dq >= 0.58 and (grade in {'A', 'B', 'C'} or has_strong_context):
            return 'noisy'
        if dq >= 0.5 and has_strong_context and supportive_ta:
            return 'noisy'
        return 'reject'

    if bucket == 'watch_candidate':
        if dq >= 0.5 and (grade in {'A', 'B', 'C'} or has_strong_context or not has_scaffold):
            return 'noisy'
        if dq >= 0.45 and has_strong_context and supportive_ta:
            return 'noisy'
        if dq >= 0.4 and has_live_fundamental and ta_score >= 1.5 and ta_decision != 'avoid':
            return 'noisy'
        return 'reject'

    if bucket == 'risk_management':
        if dq >= 0.4 or has_strong_context:
            return 'noisy'
        return 'reject'

    return 'reject'


def _learnable_row(signal: dict, outcome: dict) -> bool:
    return _row_quality(signal, outcome) in {'clean', 'noisy'}


def build_learning_summary(limit: int = 80) -> dict:
    history_rows = _load_rows(HISTORY_PATH)[-max(limit * 2, 80):]
    outcome_rows = _load_rows(OUTCOME_PATH)
    weights = load_signal_weights()
    history_index = _build_history_index(history_rows)
    latest_research_index = _load_latest_research_index()

    resolved_all: list[dict] = []
    for outcome in outcome_rows:
        if outcome.get("outcome_label") not in {"win", "loss", "flat"}:
            continue
        signal = history_index.get(str(outcome.get("signal_id", "")), {})
        signal = _merge_missing_signal_context(signal, latest_research_index)
        resolved_all.append({"signal": signal, "outcome": outcome})

    resolved_all = resolved_all[-limit:]
    resolved = [row for row in resolved_all if _learnable_row(row.get('signal', {}), row.get('outcome', {}))]
    clean_resolved = [row for row in resolved if _row_quality(row.get('signal', {}), row.get('outcome', {})) == 'clean']
    noisy_resolved = [row for row in resolved if _row_quality(row.get('signal', {}), row.get('outcome', {})) == 'noisy']
    decision_mix: dict[str, int] = {}
    raw_decision_mix: dict[str, int] = {}
    rejected_mix: dict[str, int] = {}
    labels: dict[str, int] = {}
    outcome_vals: list[float] = []
    positive_sentiment: list[float] = []
    negative_sentiment: list[float] = []
    trend_up: list[float] = []
    trend_down: list[float] = []
    overlap_high: list[float] = []
    overlap_low: list[float] = []
    evidence_high: list[float] = []
    evidence_low: list[float] = []
    study_high: list[float] = []
    study_low: list[float] = []
    playbook_yes: list[float] = []
    playbook_no: list[float] = []
    data_good: list[float] = []
    data_bad: list[float] = []
    evidence_grade_perf: dict[str, list[float]] = {}
    horizons: dict[str, list[float]] = {'h1d': [], 'h3d': [], 'h5d': [], 'h20d': []}

    for row in resolved_all:
        signal = row["signal"]
        outcome = row["outcome"]
        decision = str(outcome.get("decision") or signal.get("decision") or "unknown")
        raw_decision_mix[decision] = raw_decision_mix.get(decision, 0) + 1
        if not _learnable_row(signal, outcome):
            rejected_mix[decision] = rejected_mix.get(decision, 0) + 1

    for row in resolved:
        signal = row["signal"]
        outcome = row["outcome"]
        decision = str(outcome.get("decision") or signal.get("decision") or "unknown")
        bucket = _decision_bucket(decision)
        decision_mix[bucket] = decision_mix.get(bucket, 0) + 1
        label = str(outcome.get("outcome_label", "pending"))
        labels[label] = labels.get(label, 0) + 1
        outcome_pct = float(outcome.get("outcome_pct", 0.0))
        outcome_vals.append(outcome_pct)
        for h in horizons:
            if outcome.get(h) not in (None, ''):
                horizons[h].append(float(outcome[h]))
        features = signal.get("features", {}) if isinstance(signal, dict) else {}
        sentiment_label = str(features.get("sentiment_label", "neutral"))
        if sentiment_label == "positive":
            positive_sentiment.append(outcome_pct)
        elif sentiment_label == "negative":
            negative_sentiment.append(outcome_pct)
        trend = str(features.get("trend", "flat"))
        if trend == "up":
            trend_up.append(outcome_pct)
        elif trend == "down":
            trend_down.append(outcome_pct)
        overlap = float(features.get("theme_overlap_penalty", 0.0) or 0.0)
        if overlap >= 0.2:
            overlap_high.append(outcome_pct)
        else:
            overlap_low.append(outcome_pct)
        evidence_score = float(features.get("evidence_score", 0.0) or 0.0)
        if evidence_score >= 0.68:
            evidence_high.append(outcome_pct)
        else:
            evidence_low.append(outcome_pct)
        study_score = float(features.get("study_alignment_score", 0.0) or 0.0)
        if study_score >= 0.65:
            study_high.append(outcome_pct)
        else:
            study_low.append(outcome_pct)
        data_quality_score = float(features.get('data_quality_score', 0.0) or 0.0)
        if data_quality_score >= 0.75:
            data_good.append(outcome_pct)
        else:
            data_bad.append(outcome_pct)
        playbooks = features.get("playbooks", []) or []
        if playbooks:
            playbook_yes.append(outcome_pct)
        else:
            playbook_no.append(outcome_pct)
        grade = str(features.get("evidence_grade", "?"))
        evidence_grade_perf.setdefault(grade, []).append(outcome_pct)

    avg_outcome = round(mean(outcome_vals), 2) if outcome_vals else 0.0
    win_rate = 0.0
    decisive = labels.get("win", 0) + labels.get("loss", 0)
    if decisive:
        win_rate = round((labels.get("win", 0) / decisive) * 100, 1)

    suggestion = "Málo dat pro adaptaci vah."
    if resolved:
        if avg_outcome >= 1.25 and win_rate >= 55:
            suggestion = "Research stack funguje slušně. Drž filtraci a jemně dolaďuj váhy evidence, playbooků a datové kvality."
        elif avg_outcome >= 0.0:
            suggestion = "Bot je použitelný, ale potřebuje lépe trestat přeplněná témata, slabé důkazy a nekvalitní data."
        else:
            suggestion = "Historické výsledky jsou slabé. Zpřísnit výběr, důkazní vrstvu a obranný filtr."

    diagnostics = {
        "positive_sentiment_avg": round(mean(positive_sentiment), 2) if positive_sentiment else None,
        "negative_sentiment_avg": round(mean(negative_sentiment), 2) if negative_sentiment else None,
        "trend_up_avg": round(mean(trend_up), 2) if trend_up else None,
        "trend_down_avg": round(mean(trend_down), 2) if trend_down else None,
        "overlap_high_avg": round(mean(overlap_high), 2) if overlap_high else None,
        "overlap_low_avg": round(mean(overlap_low), 2) if overlap_low else None,
        "evidence_high_avg": round(mean(evidence_high), 2) if evidence_high else None,
        "evidence_low_avg": round(mean(evidence_low), 2) if evidence_low else None,
        "study_high_avg": round(mean(study_high), 2) if study_high else None,
        "study_low_avg": round(mean(study_low), 2) if study_low else None,
        "playbook_yes_avg": round(mean(playbook_yes), 2) if playbook_yes else None,
        "playbook_no_avg": round(mean(playbook_no), 2) if playbook_no else None,
        "data_good_avg": round(mean(data_good), 2) if data_good else None,
        "data_bad_avg": round(mean(data_bad), 2) if data_bad else None,
        "horizons": {k: (round(mean(v), 2) if v else None) for k, v in horizons.items()},
        "evidence_grade_avg": {k: round(mean(v), 2) for k, v in evidence_grade_perf.items() if v},
        "feedback": _feedback_bias(),
    }

    return {
        "count": len(resolved),
        "raw_count": len(resolved_all),
        "clean_count": len(clean_resolved),
        "noisy_count": len(noisy_resolved),
        "avg_outcome": avg_outcome,
        "win_rate": win_rate,
        "decision_mix": decision_mix,
        "raw_decision_mix": raw_decision_mix,
        "rejected_mix": rejected_mix,
        "labels": labels,
        "weights": weights,
        "suggestion": suggestion,
        "diagnostics": diagnostics,
    }


def adapt_signal_weights(limit: int = 80) -> dict:
    summary = build_learning_summary(limit=limit)
    weights = summary["weights"].copy()
    diagnostics = summary.get("diagnostics", {})

    pos = diagnostics.get("positive_sentiment_avg")
    neg = diagnostics.get("negative_sentiment_avg")
    if pos is not None and neg is not None:
        if pos > neg:
            weights["sentiment"] = min(1.8, round(weights["sentiment"] + 0.05, 2))
        else:
            weights["sentiment"] = max(0.7, round(weights["sentiment"] - 0.05, 2))

    trend_up = diagnostics.get("trend_up_avg")
    trend_down = diagnostics.get("trend_down_avg")
    if trend_up is not None and trend_down is not None:
        if trend_up >= trend_down:
            weights["trend"] = min(1.8, round(weights["trend"] + 0.05, 2))
            weights["momentum"] = min(1.8, round(weights["momentum"] + 0.05, 2))
        else:
            weights["trend"] = max(0.7, round(weights["trend"] - 0.05, 2))

    overlap_high = diagnostics.get("overlap_high_avg")
    overlap_low = diagnostics.get("overlap_low_avg")
    if overlap_high is not None and overlap_low is not None and overlap_high < overlap_low:
        weights["risk_penalty"] = min(1.8, round(weights["risk_penalty"] + 0.08, 2))

    evidence_high = diagnostics.get("evidence_high_avg")
    evidence_low = diagnostics.get("evidence_low_avg")
    if evidence_high is not None and evidence_low is not None:
        if evidence_high >= evidence_low:
            weights["evidence_quality"] = min(1.8, round(weights["evidence_quality"] + 0.06, 2))
        else:
            weights["evidence_quality"] = max(0.7, round(weights["evidence_quality"] - 0.05, 2))

    data_good = diagnostics.get('data_good_avg')
    data_bad = diagnostics.get('data_bad_avg')
    if data_good is not None and data_bad is not None:
        if data_good >= data_bad:
            weights['momentum'] = min(1.8, round(weights['momentum'] + 0.03, 2))
        else:
            weights['risk_penalty'] = min(1.8, round(weights['risk_penalty'] + 0.06, 2))
            weights['trend'] = max(0.7, round(weights['trend'] - 0.03, 2))

    study_high = diagnostics.get("study_high_avg")
    study_low = diagnostics.get("study_low_avg")
    if study_high is not None and study_low is not None:
        if study_high >= study_low:
            weights["study_alignment"] = min(1.8, round(weights["study_alignment"] + 0.04, 2))
        else:
            weights["study_alignment"] = max(0.7, round(weights["study_alignment"] - 0.04, 2))

    playbook_yes = diagnostics.get("playbook_yes_avg")
    playbook_no = diagnostics.get("playbook_no_avg")
    if playbook_yes is not None and playbook_no is not None:
        if playbook_yes >= playbook_no:
            weights["playbook_alignment"] = min(1.8, round(weights["playbook_alignment"] + 0.05, 2))
        else:
            weights["playbook_alignment"] = max(0.7, round(weights["playbook_alignment"] - 0.05, 2))

    horizons = diagnostics.get('horizons', {}) if isinstance(diagnostics.get('horizons'), dict) else {}
    h5 = horizons.get('h5d')
    h20 = horizons.get('h20d')
    if h5 is not None and h20 is not None:
        if h20 >= h5 >= 0:
            weights['regime_alignment'] = min(1.8, round(weights['regime_alignment'] + 0.04, 2))
        elif h20 < 0 and h5 < 0:
            weights['risk_penalty'] = min(1.8, round(weights['risk_penalty'] + 0.05, 2))

    if summary["avg_outcome"] < 0:
        weights["regime_alignment"] = min(1.8, round(weights["regime_alignment"] + 0.05, 2))
    elif summary["avg_outcome"] > 1.0:
        weights["regime_alignment"] = max(0.8, round(weights["regime_alignment"] - 0.02, 2))

    feedback = diagnostics.get("feedback", {}) if isinstance(diagnostics.get("feedback"), dict) else {}
    overall_feedback = feedback.get("overall_feedback_avg")
    if overall_feedback is not None:
        if overall_feedback >= 1.2:
            weights["momentum"] = min(1.8, round(weights["momentum"] + 0.03, 2))
        elif overall_feedback <= -1.0:
            weights["risk_penalty"] = min(1.8, round(weights["risk_penalty"] + 0.05, 2))
            weights["sentiment"] = max(0.7, round(weights["sentiment"] - 0.03, 2))

    _save_weights(weights)
    return weights


def run_learning_review(limit: int = 80) -> str:
    summary = build_learning_summary(limit=limit)
    lines = []
    lines.append("PŘEHLED UČENÍ – AUTO VRSTVA")
    lines.append(f"Vyhodnocené vzorky pro učení: {summary['count']}")
    lines.append(f"Všechny resolved vzorky: {summary.get('raw_count', summary['count'])}")
    lines.append(f"Čisté vzorky: {summary.get('clean_count', 0)}")
    lines.append(f"Noisy vzorky: {summary.get('noisy_count', 0)}")
    lines.append(f"Průměrný outcome: {summary['avg_outcome']}%")
    lines.append(f"Win rate: {summary['win_rate']}%")
    lines.append("Mix rozhodnutí pro učení:")
    for key, value in summary["decision_mix"].items():
        lines.append(f"- {key}: {value}")
    lines.append("Raw mix rozhodnutí:")
    for key, value in summary.get('raw_decision_mix', {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("Odmítnuté raw buckety:")
    for key, value in summary.get('rejected_mix', {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("Štítky:")
    for key, value in summary["labels"].items():
        lines.append(f"- {key}: {value}")
    lines.append("Diagnostika:")
    for key, value in summary["diagnostics"].items():
        lines.append(f"- {key}: {value}")
    lines.append("Váhy:")
    for key, value in summary["weights"].items():
        lines.append(f"- {key}: {value}")
    lines.append(f"Doporučení: {summary['suggestion']}")
    output = "\n".join(lines)
    Path("learning_review.txt").write_text(output, encoding="utf-8")
    return output


def run_rebalance_weights(limit: int = 80) -> str:
    before = load_signal_weights()
    after = adapt_signal_weights(limit=limit)
    lines = []
    lines.append("REBALANCE VAH – AUTO VRSTVA")
    for key in DEFAULT_WEIGHTS:
        lines.append(f"- {key}: {before.get(key)} -> {after.get(key)}")
    lines.append(f"Soubor vah: {WEIGHTS_PATH}")
    return "\n".join(lines)
