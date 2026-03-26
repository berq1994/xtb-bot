from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

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
    bias: dict[str, float] = {"overall_feedback_avg": round(avg_usefulness, 2)}
    pos = [float(r.get("usefulness", 0.0)) for r in rows if str(r.get("sentiment_label", "")) == "positive"]
    neg = [float(r.get("usefulness", 0.0)) for r in rows if str(r.get("sentiment_label", "")) == "negative"]
    if pos:
        bias["feedback_positive_avg"] = round(mean(pos), 2)
    if neg:
        bias["feedback_negative_avg"] = round(mean(neg), 2)
    return bias


def build_learning_summary(limit: int = 50) -> dict:
    history_rows = _load_rows(HISTORY_PATH)[-max(limit * 2, 50):]
    outcome_rows = _load_rows(OUTCOME_PATH)
    weights = load_signal_weights()
    history_index = _build_history_index(history_rows)

    resolved: list[dict] = []
    for outcome in outcome_rows:
        if outcome.get("outcome_label") not in {"win", "loss", "flat"}:
            continue
        signal = history_index.get(str(outcome.get("signal_id", "")), {})
        resolved.append({"signal": signal, "outcome": outcome})

    resolved = resolved[-limit:]
    decision_mix: dict[str, int] = {}
    labels: dict[str, int] = {}
    outcome_vals: list[float] = []
    positive_sentiment: list[float] = []
    negative_sentiment: list[float] = []
    trend_up: list[float] = []
    trend_down: list[float] = []
    overlap_high: list[float] = []
    overlap_low: list[float] = []
    data_source_perf: dict[str, list[float]] = {}
    news_provider_perf: dict[str, list[float]] = {}

    for row in resolved:
        signal = row["signal"]
        outcome = row["outcome"]
        decision = str(outcome.get("decision") or signal.get("decision") or "unknown")
        decision_mix[decision] = decision_mix.get(decision, 0) + 1
        label = str(outcome.get("outcome_label", "pending"))
        labels[label] = labels.get(label, 0) + 1
        outcome_pct = float(outcome.get("outcome_pct", 0.0))
        outcome_vals.append(outcome_pct)
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
        data_source = str(features.get("data_source") or signal.get("source") or "unknown")
        data_source_perf.setdefault(data_source, []).append(outcome_pct)
        for provider in features.get("news_providers", []) or []:
            news_provider_perf.setdefault(str(provider), []).append(outcome_pct)

    avg_outcome = round(mean(outcome_vals), 2) if outcome_vals else 0.0
    win_rate = 0.0
    decisive = labels.get("win", 0) + labels.get("loss", 0)
    if decisive:
        win_rate = round((labels.get("win", 0) / decisive) * 100, 1)

    suggestion = "Málo dat pro adaptaci vah."
    if resolved:
        if avg_outcome >= 1.25 and win_rate >= 55:
            suggestion = "Research stack funguje slušně. Drž filtraci a jen jemně dolaďuj váhy."
        elif avg_outcome >= 0.0:
            suggestion = "Bot je použitelný, ale potřebuje lépe trestat přeplněná témata a slabé zprávy."
        else:
            suggestion = "Historické výsledky jsou slabé. Zpřísnit výběr, sentiment a risk overlay."

    diagnostics = {
        "positive_sentiment_avg": round(mean(positive_sentiment), 2) if positive_sentiment else None,
        "negative_sentiment_avg": round(mean(negative_sentiment), 2) if negative_sentiment else None,
        "trend_up_avg": round(mean(trend_up), 2) if trend_up else None,
        "trend_down_avg": round(mean(trend_down), 2) if trend_down else None,
        "overlap_high_avg": round(mean(overlap_high), 2) if overlap_high else None,
        "overlap_low_avg": round(mean(overlap_low), 2) if overlap_low else None,
        "best_data_source": None,
        "worst_data_source": None,
        "best_news_provider": None,
        "feedback": _feedback_bias(),
    }

    if data_source_perf:
        src_avg = {k: round(mean(v), 2) for k, v in data_source_perf.items() if v}
        if src_avg:
            diagnostics["best_data_source"] = max(src_avg, key=src_avg.get)
            diagnostics["worst_data_source"] = min(src_avg, key=src_avg.get)
            diagnostics["data_source_avg"] = src_avg
    if news_provider_perf:
        provider_avg = {k: round(mean(v), 2) for k, v in news_provider_perf.items() if v}
        if provider_avg:
            diagnostics["best_news_provider"] = max(provider_avg, key=provider_avg.get)
            diagnostics["news_provider_avg"] = provider_avg

    return {
        "count": len(resolved),
        "avg_outcome": avg_outcome,
        "win_rate": win_rate,
        "decision_mix": decision_mix,
        "labels": labels,
        "weights": weights,
        "suggestion": suggestion,
        "diagnostics": diagnostics,
    }


def adapt_signal_weights(limit: int = 50) -> dict:
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


def run_learning_review(limit: int = 50) -> str:
    summary = build_learning_summary(limit=limit)

    lines = []
    lines.append("PŘEHLED UČENÍ – FÁZE 5")
    lines.append(f"Vyhodnocené vzorky: {summary['count']}")
    lines.append(f"Průměrný outcome: {summary['avg_outcome']}%")
    lines.append(f"Win rate: {summary['win_rate']}%")
    lines.append("Mix rozhodnutí:")
    for key, value in summary["decision_mix"].items():
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


def run_rebalance_weights(limit: int = 50) -> str:
    before = load_signal_weights()
    after = adapt_signal_weights(limit=limit)

    lines = []
    lines.append("REBALANCE VAH – FÁZE 5")
    for key in DEFAULT_WEIGHTS:
        lines.append(f"- {key}: {before.get(key)} -> {after.get(key)}")
    lines.append(f"Soubor vah: {WEIGHTS_PATH}")
    return "\n".join(lines)
