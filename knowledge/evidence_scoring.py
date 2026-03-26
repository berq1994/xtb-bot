from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

SOURCE_TRUST = {
    "reuters": 1.0,
    "bloomberg": 0.98,
    "wsj": 0.95,
    "wall street journal": 0.95,
    "financial times": 0.94,
    "cnbc": 0.88,
    "marketwatch": 0.8,
    "yahoo finance": 0.72,
    "fmp": 0.74,
    "google news": 0.68,
    "scaffold": 0.2,
}

PROVIDER_TRUST = {
    "google_news_rss": 0.74,
    "fmp_news": 0.7,
    "scaffold": 0.2,
}


def _trust_for_source(name: str) -> float:
    text = str(name or "").strip().lower()
    if not text:
        return 0.35
    for key, value in SOURCE_TRUST.items():
        if key in text:
            return value
    return 0.5


def _trust_for_provider(name: str) -> float:
    text = str(name or "").strip().lower()
    return PROVIDER_TRUST.get(text, 0.45)


def _recency_bonus(published: str) -> float:
    if not published:
        return 0.0
    dt = None
    try:
        dt = parsedate_to_datetime(published)
    except Exception:
        try:
            dt = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
        except Exception:
            return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    if age_hours <= 12:
        return 0.08
    if age_hours <= 48:
        return 0.04
    return 0.0


def _grade(score: float) -> str:
    if score >= 0.82:
        return "A"
    if score >= 0.68:
        return "B"
    if score >= 0.52:
        return "C"
    return "D"


def score_news_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "score": 0.2,
            "grade": "D",
            "trusted_sources": [],
            "providers": [],
            "reasons": ["bez zpráv = minimální důkazní síla"],
        }
    raw_scores: list[float] = []
    sources: list[str] = []
    providers: list[str] = []
    reasons: list[str] = []
    for item in items[:6]:
        source = str(item.get("source") or "").strip()
        provider = str(item.get("provider") or "").strip()
        sources.append(source)
        providers.append(provider)
        score = (_trust_for_source(source) * 0.7) + (_trust_for_provider(provider) * 0.3) + _recency_bonus(str(item.get("published") or ""))
        raw_scores.append(min(1.0, round(score, 3)))
    unique_sources = sorted({s for s in sources if s})
    unique_providers = sorted({p for p in providers if p})
    avg_score = sum(raw_scores) / len(raw_scores)
    if len(unique_sources) >= 2:
        avg_score += 0.05
        reasons.append("více zdrojů potvrzuje stejné téma")
    if any(_trust_for_source(s) >= 0.9 for s in unique_sources):
        reasons.append("přítomen vysoce důvěryhodný zdroj")
    if any(_trust_for_provider(p) <= 0.25 for p in unique_providers):
        avg_score -= 0.08
        reasons.append("část zpráv je jen scaffold / slabý provider")
    avg_score = max(0.0, min(1.0, round(avg_score, 2)))
    grade = _grade(avg_score)
    if not reasons:
        reasons.append("standardní kvalita důkazů")
    return {
        "score": avg_score,
        "grade": grade,
        "trusted_sources": unique_sources[:4],
        "providers": unique_providers[:4],
        "reasons": reasons[:3],
    }
