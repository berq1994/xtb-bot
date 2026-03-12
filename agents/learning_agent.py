from __future__ import annotations

import json
from pathlib import Path


HISTORY_PATH = Path("data/openbb_signal_history.jsonl")
WEIGHTS_PATH = Path("data/phase5_signal_weights.json")


DEFAULT_WEIGHTS = {
    "trend": 1.0,
    "momentum": 1.0,
    "sentiment": 1.0,
    "regime_alignment": 1.0,
    "risk_penalty": 1.0,
}


def _load_rows():
    if not HISTORY_PATH.exists():
        return []

    rows = []
    with HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _load_weights():
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


def build_learning_summary(limit: int = 25) -> dict:
    rows = _load_rows()[-limit:]
    weights = _load_weights()

    decision_mix = {}
    score_total = 0.0

    for row in rows:
        decision = row.get("decision", "unknown")
        decision_mix[decision] = decision_mix.get(decision, 0) + 1

        score = 0.0
        regime = row.get("regime", "mixed")
        if regime == "risk_on":
            score += 3.0
        elif regime == "mixed":
            score += 2.0
        else:
            score += 1.0

        if row.get("ticket_symbol"):
            score += 1.0

        score_total += score

    avg_quality = round(score_total / len(rows), 2) if rows else 0.0

    suggestion = "Málo dat pro adaptaci vah."
    if rows:
        if avg_quality >= 3.0:
            suggestion = "Současný signal stack vypadá zdravě."
        elif avg_quality >= 2.0:
            suggestion = "Systém je použitelný, ale měl by tvrději filtrovat slabé setupy."
        else:
            suggestion = "Kvalita signálů je nízká. Zpřísnit vstupní podmínky."

    return {
        "count": len(rows),
        "avg_quality": avg_quality,
        "decision_mix": decision_mix,
        "weights": weights,
        "suggestion": suggestion,
    }


def adapt_signal_weights(limit: int = 25) -> dict:
    summary = build_learning_summary(limit=limit)
    weights = summary["weights"].copy()

    avg_quality = summary["avg_quality"]
    if avg_quality < 2.0:
        weights["risk_penalty"] = round(weights["risk_penalty"] + 0.1, 2)
        weights["sentiment"] = round(weights["sentiment"] + 0.1, 2)
    elif avg_quality >= 3.0:
        weights["trend"] = round(weights["trend"] + 0.1, 2)
        weights["momentum"] = round(weights["momentum"] + 0.1, 2)

    _save_weights(weights)
    return weights


def run_learning_review(limit: int = 25) -> str:
    summary = build_learning_summary(limit=limit)

    lines = []
    lines.append("PŘEHLED UČENÍ – FÁZE 5")
    lines.append(f"Počet vzorků historie: {summary['count']}")
    lines.append(f"Průměrné skóre kvality: {summary['avg_quality']}")
    lines.append("Mix rozhodnutí:")

    for key, value in summary["decision_mix"].items():
        lines.append(f"- {key}: {value}")

    lines.append("Váhy:")
    for key, value in summary["weights"].items():
        lines.append(f"- {key}: {value}")

    lines.append(f"Doporučení: {summary['suggestion']}")
    output = "\n".join(lines)
    Path("learning_review.txt").write_text(output, encoding="utf-8")
    return output


def run_rebalance_weights(limit: int = 25) -> str:
    before = _load_weights()
    after = adapt_signal_weights(limit=limit)

    lines = []
    lines.append("REBALANCE VAH – FÁZE 5")
    for key in DEFAULT_WEIGHTS:
        lines.append(f"- {key}: {before.get(key)} -> {after.get(key)}")
    lines.append(f"Soubor vah: {WEIGHTS_PATH}")
    return "\n".join(lines)