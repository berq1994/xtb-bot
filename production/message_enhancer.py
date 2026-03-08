import re
from typing import List, Dict

BRIEFING_RE = re.compile(
    r"^- \[(?P<category>[^\]]+)\] (?P<title>.*?) \| impact (?P<impact>\d+(?:\.\d+)?) \| relevance (?P<relevance>\d+(?:\.\d+)?)$",
    re.IGNORECASE,
)

ALERT_RE = re.compile(
    r"^\[(?P<category>[^\]]+)\] (?P<title>.*?) \| tickers: (?P<tickers>.*?) \| impact (?P<impact>\d+(?:\.\d+)?)$",
    re.IGNORECASE,
)

ACTION_MAP = {
    "geo": "Sledovat energie a dopravu, čekat vyšší volatilitu.",
    "earnings": "Pozor na gap risk, menší size a opatrnost přes close.",
    "macro": "Sledovat indexy a sentiment, zatím spíš watchlist.",
    "corporate": "Prověřit filing a reakci trhu, zatím potvrdit price action.",
}

RISK_MAP = {
    "geo": "Riziko headline volatility a rychlých reverzů.",
    "earnings": "Riziko gapu mimo stop a prudkého rozšíření spreadů.",
    "macro": "Riziko falešného intradenního směru po datech.",
    "corporate": "Riziko slabé relevance bez follow-through objemu.",
}


def _priority_from_impact(impact: float) -> str:
    if impact >= 0.80:
        return "HIGH"
    if impact >= 0.67:
        return "MEDIUM"
    return "LOW"


def _confidence(impact: float, relevance: float | None = None) -> float:
    if relevance is None:
        return round(impact, 2)
    return round((impact * 0.6) + (relevance * 0.4), 2)


def parse_briefing_items(briefing_text: str) -> List[Dict]:
    items: List[Dict] = []
    for raw in briefing_text.splitlines():
        match = BRIEFING_RE.match(raw.strip())
        if not match:
            continue
        category = match.group("category").strip().lower()
        impact = float(match.group("impact"))
        relevance = float(match.group("relevance"))
        items.append(
            {
                "category": category,
                "title": match.group("title").strip(),
                "impact": impact,
                "relevance": relevance,
                "priority": _priority_from_impact(impact),
                "confidence": _confidence(impact, relevance),
                "action": ACTION_MAP.get(category, "Sledovat další potvrzení a price action."),
                "risk_note": RISK_MAP.get(category, "Riziko šumu bez obchodovatelného follow-through."),
            }
        )
    return items


def parse_alert_lines(alert_lines: List[str]) -> List[Dict]:
    items: List[Dict] = []
    seen = set()
    for raw in alert_lines:
        match = ALERT_RE.match(raw.strip())
        if not match:
            continue
        category = match.group("category").strip().lower()
        title = match.group("title").strip()
        tickers = [x.strip() for x in match.group("tickers").split(",") if x.strip()]
        impact = float(match.group("impact"))
        dedupe_key = (category, title, tuple(tickers))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(
            {
                "category": category,
                "title": title,
                "tickers": tickers,
                "impact": impact,
                "priority": _priority_from_impact(impact),
                "confidence": _confidence(impact),
                "action": ACTION_MAP.get(category, "Sledovat další potvrzení a price action."),
                "risk_note": RISK_MAP.get(category, "Riziko šumu bez obchodovatelného follow-through."),
            }
        )
    return items


def render_briefing_message(briefing_text: str, items: List[Dict]) -> str:
    if not items:
        return briefing_text.strip() or "Briefing zatím není."

    counts = {}
    for item in items:
        counts[item["category"].upper()] = counts.get(item["category"].upper(), 0) + 1
    header_counts = " | ".join(f"{k}: {v}" for k, v in counts.items())

    lines = [
        "🧠 Live Intelligence Briefing",
        header_counts,
        "",
    ]
    for idx, item in enumerate(items, start=1):
        tick = "🔴" if item["priority"] == "HIGH" else "🟡" if item["priority"] == "MEDIUM" else "🟢"
        lines.extend(
            [
                f"{idx}) {tick} {item['category'].upper()} | {item['priority']}",
                item["title"],
                f"Confidence: {item['confidence']:.2f} | Impact: {item['impact']:.3f}",
                f"Akce: {item['action']}",
                f"Riziko: {item['risk_note']}",
                "",
            ]
        )
    return "\n".join(lines).strip()[:4096]


def render_alerts_message(alerts: List[Dict]) -> str:
    if not alerts:
        return "Žádné alerty."

    lines = ["🚨 XTB Live Alerts", ""]
    for idx, item in enumerate(alerts, start=1):
        tick = "🔴" if item["priority"] == "HIGH" else "🟡" if item["priority"] == "MEDIUM" else "🟢"
        tickers = ", ".join(item.get("tickers", [])) or "N/A"
        lines.extend(
            [
                f"{idx}) {tick} {item['category'].upper()} | {item['priority']}",
                item["title"],
                f"Tickery: {tickers}",
                f"Confidence: {item['confidence']:.2f} | Impact: {item['impact']:.3f}",
                f"Akce: {item['action']}",
                f"Riziko: {item['risk_note']}",
                "",
            ]
        )
    return "\n".join(lines).strip()[:4096]
