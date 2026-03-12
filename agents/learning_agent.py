from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from agents.signal_history_agent import HISTORY_PATH, build_snapshot_payload
from cz_utils import decision_cs

WEIGHTS_PATH = Path("data/phase5_signal_weights.json")
REPORT_PATH = Path("data/phase5_learning_report.txt")

DEFAULT_WEIGHTS = {
    "trend": 1.0,
    "momentum": 1.0,
    "sentiment": 1.0,
    "regime_alignment": 1.0,
    "risk_penalty": 1.0,
}


def _load_history(limit: int = 50) -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    rows: list[dict] = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def _load_weights() -> dict:
    if not WEIGHTS_PATH.exists():
        WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        WEIGHTS_PATH.write_text(json.dumps(DEFAULT_WEIGHTS, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(DEFAULT_WEIGHTS)
    try:
        data = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_WEIGHTS)
        merged.update({k: float(v) for k, v in data.items() if k in DEFAULT_WEIGHTS})
        return merged
    except Exception:
        return dict(DEFAULT_WEIGHTS)


def _save_weights(weights: dict) -> None:
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_PATH.write_text(json.dumps(weights, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_quality(payload: dict) -> float:
    score = 0.0
    regime = payload.get("regime", "mixed")
    decision = payload.get("supervisor", {}).get("decision", "wait")
    leader = payload.get("leader") or {}
    laggard = payload.get("laggard") or {}
    ticket = payload.get("ticket") or {}

    if decision == "watch_long":
        score += 1.0
    elif decision == "watch_hedge":
        score += 0.4
    elif decision == "defensive_only":
        score += 0.2

    if leader.get("trend") == "up":
        score += 0.7
    if float(leader.get("change_pct", 0) or 0) > 0.4:
        score += 0.7

    sentiment = leader.get("sentiment_label", ticket.get("news_sentiment", "neutral"))
    if sentiment == "positive":
        score += 0.8
    elif sentiment == "negative":
        score -= 0.6

    if regime == "risk_on" and decision == "watch_long":
        score += 0.9
    elif regime == "mixed" and decision == "watch_long":
        score += 0.4
    elif regime == "risk_off" and decision == "watch_long":
        score -= 1.0

    if float(laggard.get("change_pct", 0) or 0) < -1.0:
        score += 0.2

    rr = 0.0
    entry = float(ticket.get("entry_reference", 0) or 0)
    sl = float(ticket.get("stop_loss", 0) or 0)
    tp = float(ticket.get("take_profit", 0) or 0)
    if entry and sl and tp and abs(entry - sl) > 0:
        rr = abs(tp - entry) / abs(entry - sl)
    score += min(rr, 3.0) * 0.25
    return round(score, 2)


def build_learning_summary(limit: int = 25) -> dict:
    history = _load_history(limit=limit)
    weights = _load_weights()
    if not history:
        payload = build_snapshot_payload()
        return {
            "count": 0,
            "avg_quality": _snapshot_quality(payload),
            "decision_mix": {payload.get("supervisor", {}).get("decision", "wait"): 1},
            "weights": weights,
            "suggestion": "NejdĹ™Ă­v nasbĂ­rej vĂ­ce historie, teprve pak agresivnÄ›ji upravuj vĂˇhy.",
        }

    qualities = [_snapshot_quality(row) for row in history]
    decision_mix: dict[str, int] = {}
    long_wins = 0
    negative_sentiment_count = 0
    for row in history:
        decision = row.get("supervisor", {}).get("decision", "wait")
        decision_mix[decision] = decision_mix.get(decision, 0) + 1
        leader = row.get("leader") or {}
        if decision == "watch_long" and leader.get("trend") == "up" and float(leader.get("change_pct", 0) or 0) > 0.4:
            long_wins += 1
        if leader.get("sentiment_label") == "negative":
            negative_sentiment_count += 1

    avg_quality = round(mean(qualities), 2)
    long_share = decision_mix.get("watch_long", 0) / max(len(history), 1)

    suggestion_parts = []
    if avg_quality >= 2.4:
        suggestion_parts.append("SouÄŤasnĂ˝ signĂˇlovĂ˝ stack vypadĂˇ zdravÄ›.")
    elif avg_quality >= 1.6:
        suggestion_parts.append("SystĂ©m je stabilnĂ­, ale mÄ›l by pĹ™Ă­snÄ›ji filtrovat prĹŻmÄ›rnĂ© setupy.")
    else:
        suggestion_parts.append("Kvalita signĂˇlĹŻ je slabĹˇĂ­; zpĹ™Ă­sni vstupy a uber agresivitu.")

    if long_share > 0.65:
        suggestion_parts.append("Long watchĹŻ je pĹ™Ă­liĹˇ mnoho vĹŻÄŤi celkovĂ©mu toku signĂˇlĹŻ.")
    if negative_sentiment_count > len(history) * 0.25:
        suggestion_parts.append("NegativnĂ­ tok zprĂˇv se v lead setupech objevuje pĹ™Ă­liĹˇ ÄŤasto.")
    if long_wins >= max(3, len(history) // 3):
        suggestion_parts.append("Soulad trendu a momenta funguje dobĹ™e.")

    return {
        "count": len(history),
        "avg_quality": avg_quality,
        "decision_mix": decision_mix,
        "weights": weights,
        "suggestion": " ".join(suggestion_parts).strip(),
    }


def adapt_signal_weights(limit: int = 25) -> dict:
    summary = build_learning_summary(limit=limit)
    weights = dict(summary["weights"])
    avg_quality = float(summary["avg_quality"])
    decision_mix = summary["decision_mix"]

    if avg_quality >= 2.4:
        weights["trend"] = round(min(weights["trend"] + 0.08, 1.6), 2)
        weights["momentum"] = round(min(weights["momentum"] + 0.08, 1.6), 2)
        weights["sentiment"] = round(min(weights["sentiment"] + 0.05, 1.5), 2)
    elif avg_quality < 1.6:
        weights["risk_penalty"] = round(min(weights["risk_penalty"] + 0.12, 1.8), 2)
        weights["sentiment"] = round(min(weights["sentiment"] + 0.06, 1.5), 2)
        weights["momentum"] = round(max(weights["momentum"] - 0.05, 0.7), 2)

    if decision_mix.get("watch_long", 0) > max(3, summary["count"] // 2):
        weights["regime_alignment"] = round(min(weights["regime_alignment"] + 0.08, 1.7), 2)

    _save_weights(weights)
    return weights


def run_learning_review(limit: int = 25) -> str:
    summary = build_learning_summary(limit=limit)
    lines = []
    lines.append("PĹEHLED UÄŚENĂŤ â€“ FĂZE 5")
    lines.append(f"PoÄŤet vzorkĹŻ historie: {summary['count']}")
    lines.append(f"PrĹŻmÄ›rnĂ© skĂłre kvality: {summary['avg_quality']}")
    lines.append("Mix rozhodnutĂ­:")
    for key, value in summary["decision_mix"].items():
        lines.append(f"- {decision_cs(key)}: {value}")
    lines.append("VĂˇhy:")
    for key, value in summary["weights"].items():
        lines.append(f"- {key}: {value}")
    lines.append(f"DoporuÄŤenĂ­: {summary['suggestion']}")
    output = "\n".join(lines)
    REPORT_PATH.write_text(output, encoding="utf-8")
    return output


def run_rebalance_weights(limit: int = 25) -> str:
    before = _load_weights()
    after = adapt_signal_weights(limit=limit)
    lines = []
    lines.append("REBALANCE VAH â€“ FĂZE 5")
    for key in DEFAULT_WEIGHTS:
        lines.append(f"- {key}: {before.get(key)} -> {after.get(key)}")
    lines.append(f"Soubor vah: {WEIGHTS_PATH}")
    return "\\n".join(lines)

