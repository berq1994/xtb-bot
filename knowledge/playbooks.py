from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PLAYBOOK_DIR = Path("knowledge/playbooks")
INDEX_PATH = Path("data/playbook_index.json")

SEED_PLAYBOOKS = [
    {
        "id": "earnings_follow_through",
        "title": "Earnings follow-through",
        "description": "Po earnings a pozitivním sentimentu udržuj vyšší prioritu jen když je trend up a evidence není slabá.",
        "category": "offense",
    },
    {
        "id": "portfolio_defense_negative_news",
        "title": "Portfolio defense on negative news",
        "description": "U držené pozice s negativním sentimentem a trendem down preferuj obranný monitoring a redukci rizika.",
        "category": "defense",
    },
    {
        "id": "breakout_with_evidence",
        "title": "Breakout backed by evidence",
        "description": "Breakout má smysl jen když momentum podporují více zdrojů nebo kvalitní provider.",
        "category": "offense",
    },
    {
        "id": "crowded_theme_penalty",
        "title": "Crowded theme penalty",
        "description": "Když je téma přeplněné v portfoliu, snižuj prioritu a čekej na silnější důkazy.",
        "category": "risk",
    },
    {
        "id": "risk_off_rotation",
        "title": "Risk-off rotation",
        "description": "V risk-off prostředí hledej obrannou rotaci, zlaté a utilitní expozice, a snižuj agresivní growth.",
        "category": "defense",
    },
    {
        "id": "winner_management",
        "title": "Winner management",
        "description": "U velkých vítězů v portfoliu sleduj přehřátí, slabší evidence nebo přechod do risk-off režimu.",
        "category": "risk",
    },
]


def ensure_seed_playbooks() -> None:
    PLAYBOOK_DIR.mkdir(parents=True, exist_ok=True)
    for row in SEED_PLAYBOOKS:
        path = PLAYBOOK_DIR / f"{row['id']}.json"
        if not path.exists():
            path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    index = {
        "count": len(list(PLAYBOOK_DIR.glob('*.json'))),
        "playbook_ids": sorted(p.stem for p in PLAYBOOK_DIR.glob('*.json')),
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_playbooks() -> list[dict[str, Any]]:
    ensure_seed_playbooks()
    rows: list[dict[str, Any]] = []
    for path in sorted(PLAYBOOK_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def evaluate_playbooks_for_item(item: dict[str, Any], regime: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    held = bool(item.get("held"))
    catalysts = {str(v).strip().lower() for v in item.get("catalysts", []) or []}
    trend = str(item.get("trend") or "flat").strip().lower()
    sentiment = str(item.get("sentiment_label") or "neutral").strip().lower()
    momentum_5d = float(item.get("momentum_5d", 0.0) or 0.0)
    pnl = item.get("pnl_vs_cost_pct")
    overlap = float(item.get("theme_overlap_penalty", 0.0) or 0.0)
    evidence_score = float(item.get("evidence_score", 0.0) or 0.0)

    for playbook in _load_playbooks():
        pid = str(playbook.get("id") or "")
        score = 0.0
        if pid == "earnings_follow_through":
            if "earnings" in catalysts:
                score += 0.35
            if trend == "up":
                score += 0.2
            if sentiment == "positive":
                score += 0.15
            if evidence_score >= 0.65:
                score += 0.15
        elif pid == "portfolio_defense_negative_news":
            if held:
                score += 0.2
            if trend == "down":
                score += 0.2
            if sentiment == "negative":
                score += 0.25
            if str(regime).lower() == "risk_off":
                score += 0.1
        elif pid == "breakout_with_evidence":
            if trend == "up":
                score += 0.25
            if momentum_5d >= 1.5:
                score += 0.2
            if evidence_score >= 0.7:
                score += 0.2
        elif pid == "crowded_theme_penalty":
            if overlap >= 0.15:
                score += 0.35
            if evidence_score < 0.55:
                score += 0.15
        elif pid == "risk_off_rotation":
            if str(regime).lower() == "risk_off":
                score += 0.35
            if any(t in {"utilities", "gold", "energy", "defense"} for t in [str(v).lower() for v in item.get("themes", []) or []]):
                score += 0.2
        elif pid == "winner_management":
            if held and pnl is not None and float(pnl) >= 12:
                score += 0.4
            if evidence_score < 0.55:
                score += 0.1
            if str(regime).lower() == "risk_off":
                score += 0.1
        if score >= 0.45:
            matches.append({
                "id": pid,
                "title": playbook.get("title"),
                "category": playbook.get("category"),
                "score": round(score, 2),
            })
    matches.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    return {
        "match_score": round(float(matches[0]["score"]), 2) if matches else 0.0,
        "matches": matches[:3],
    }
