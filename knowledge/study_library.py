from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LIBRARY_DIR = Path("knowledge/library")
INDEX_PATH = Path("data/study_library_index.json")

SEED_STUDIES = [
    {
        "id": "momentum_persistence",
        "title": "Momentum persistence after multi-day strength",
        "summary": "Akcie se silným 5d a 20d momentum mají vyšší šanci na pokračování trendu, pokud zároveň není sentiment prudce negativní.",
        "keywords": ["momentum", "trend", "breakout", "follow-through", "leadership"],
        "regimes": ["risk_on", "mixed"],
        "themes": ["ai", "semis", "software", "growth"],
        "catalysts": ["analyst", "deal", "product"],
        "base_score": 0.34,
    },
    {
        "id": "post_earnings_drift",
        "title": "Post-earnings drift and guidance follow-through",
        "summary": "Po silných výsledcích a zvýšeném guidance často následuje více denní follow-through, hlavně u kvalitních firem s více potvrzujícími zdroji.",
        "keywords": ["earnings", "guidance", "revenue", "eps", "results"],
        "regimes": ["risk_on", "mixed"],
        "themes": ["software", "cloud", "semis", "internet"],
        "catalysts": ["earnings"],
        "base_score": 0.42,
    },
    {
        "id": "risk_off_quality",
        "title": "Quality and defense in risk-off regime",
        "summary": "V risk-off režimu funguje obranná logika: snižovat slabé growth pozice, sledovat utility, zlato a kvalitní cash-flow firmy.",
        "keywords": ["risk", "defense", "quality", "drawdown", "hedge"],
        "regimes": ["risk_off"],
        "themes": ["utilities", "gold", "energy", "defense"],
        "catalysts": ["macro", "legal"],
        "base_score": 0.39,
    },
    {
        "id": "event_driven_geopolitics",
        "title": "Geopolitical event transmission",
        "summary": "Geopolitické šoky se přelévají přes energie, obranu, sazby a komodity. Relevance je vyšší u firem s přímou sektorovou citlivostí.",
        "keywords": ["geopolitics", "oil", "tariff", "sanction", "defense", "rates"],
        "regimes": ["risk_off", "mixed"],
        "themes": ["energy", "defense", "commodities", "utilities"],
        "catalysts": ["macro", "deal", "legal"],
        "base_score": 0.31,
    },
    {
        "id": "mean_reversion_drawdown",
        "title": "Controlled mean reversion after oversold drawdown",
        "summary": "Prudké propady bez tvrdého fundamentálního zlomu mohou nabídnout mean reversion, ale jen při slušné kvalitě zdrojů a známkách stabilizace.",
        "keywords": ["drawdown", "oversold", "stabilization", "rebound"],
        "regimes": ["mixed", "risk_on"],
        "themes": ["internet", "software", "growth", "crypto"],
        "catalysts": ["analyst", "earnings"],
        "base_score": 0.22,
    },
    {
        "id": "volatility_risk_filter",
        "title": "Volatility filter and evidence discipline",
        "summary": "U příliš volatilních titulů bez více kvalitních zdrojů má být priorita snížená. Vysoká volatilita sama o sobě není edge.",
        "keywords": ["volatility", "atr", "evidence", "source", "noise"],
        "regimes": ["risk_on", "risk_off", "mixed"],
        "themes": ["crypto", "growth", "smallcap", "ai"],
        "catalysts": ["macro", "product", "analyst"],
        "base_score": 0.28,
    },
]


def ensure_seed_studies() -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    for row in SEED_STUDIES:
        path = LIBRARY_DIR / f"{row['id']}.json"
        if not path.exists():
            path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    index = {
        "count": len(list(LIBRARY_DIR.glob('*.json'))),
        "study_ids": sorted(p.stem for p in LIBRARY_DIR.glob('*.json')),
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def load_studies() -> list[dict[str, Any]]:
    ensure_seed_studies()
    rows: list[dict[str, Any]] = []
    for path in sorted(LIBRARY_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _keywords_for_item(item: dict[str, Any], regime: str) -> set[str]:
    words: set[str] = set()
    words.add(str(regime or "mixed").strip().lower())
    words.add(str(item.get("trend") or "flat").strip().lower())
    category = str(item.get("category") or "").strip().lower()
    if category:
        words.add(category)
    for value in item.get("themes", []) or []:
        text = str(value).strip().lower()
        if text:
            words.add(text)
    for value in item.get("catalysts", []) or []:
        text = str(value).strip().lower()
        if text:
            words.add(text)
    sentiment = str(item.get("sentiment_label") or "neutral").strip().lower()
    words.add(sentiment)
    if float(item.get("momentum_5d", 0.0) or 0.0) >= 2.0:
        words.add("momentum")
        words.add("breakout")
    if float(item.get("theme_overlap_penalty", 0.0) or 0.0) > 0.15:
        words.add("crowded")
    if float(item.get("atr_proxy_pct", 0.0) or 0.0) >= 4.0:
        words.add("volatility")
    if item.get("held"):
        words.add("held")
    return words


def match_studies_for_item(item: dict[str, Any], regime: str) -> dict[str, Any]:
    studies = load_studies()
    item_words = _keywords_for_item(item, regime)
    matched: list[dict[str, Any]] = []
    notes: list[str] = []
    best_score = 0.0
    for study in studies:
        score = float(study.get("base_score", 0.0) or 0.0)
        overlap = len(item_words.intersection({str(v).lower() for v in study.get("keywords", [])}))
        score += overlap * 0.11
        if str(regime).strip().lower() in {str(v).lower() for v in study.get("regimes", [])}:
            score += 0.14
        study_themes = {str(v).lower() for v in study.get("themes", [])}
        if item_words.intersection(study_themes):
            score += 0.12
        study_catalysts = {str(v).lower() for v in study.get("catalysts", [])}
        if item_words.intersection(study_catalysts):
            score += 0.16
        if score >= 0.45:
            matched.append(
                {
                    "id": study.get("id"),
                    "title": study.get("title"),
                    "summary": study.get("summary"),
                    "score": round(score, 2),
                }
            )
            if score > best_score:
                best_score = score
    matched.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    if matched:
        notes.append(f"studie potvrzují setup: {', '.join(str(m.get('title')) for m in matched[:2])}")
    else:
        notes.append("nenalezena silná studijní opora")
    return {
        "alignment_score": round(best_score, 2),
        "matched": matched[:3],
        "notes": notes,
        "keywords": sorted(item_words),
    }
