import re
from typing import Dict, List

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

BIAS_MAP = {
    "geo": "volatile",
    "earnings": "event-driven",
    "macro": "neutral",
    "corporate": "selective",
}

TIMEFRAME_MAP = {
    "geo": "intraday–1d",
    "earnings": "today–next session",
    "macro": "intraday",
    "corporate": "1–3 days",
}

STATUS_MAP = {
    "geo": "HIGH VOL",
    "earnings": "WATCHLIST",
    "macro": "NO TRADE",
    "corporate": "CONFIRM PRICE ACTION",
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


def _status_from(category: str, impact: float, priority: str) -> str:
    if priority == "HIGH":
        return "SETUP FORMING" if category != "macro" else "HIGH VOL"
    return STATUS_MAP.get(category, "WATCHLIST")


def _timeframe_from(category: str) -> str:
    return TIMEFRAME_MAP.get(category, "intraday")


def _bias_from(category: str, impact: float) -> str:
    base = BIAS_MAP.get(category, "neutral")
    if impact >= 0.80 and category in {"geo", "earnings"}:
        return f"{base} / elevated"
    return base


def parse_briefing_items(briefing_text: str) -> List[Dict]:
    items: List[Dict] = []
    for raw in briefing_text.splitlines():
        match = BRIEFING_RE.match(raw.strip())
        if not match:
            continue
        category = match.group("category").strip().lower()
        impact = float(match.group("impact"))
        relevance = float(match.group("relevance"))
        priority = _priority_from_impact(impact)
        items.append(
            {
                "category": category,
                "title": match.group("title").strip(),
                "impact": impact,
                "relevance": relevance,
                "priority": priority,
                "confidence": _confidence(impact, relevance),
                "action": ACTION_MAP.get(category, "Sledovat další potvrzení a price action."),
                "risk_note": RISK_MAP.get(category, "Riziko šumu bez obchodovatelného follow-through."),
                "status": _status_from(category, impact, priority),
                "timeframe": _timeframe_from(category),
                "bias": _bias_from(category, impact),
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
        priority = _priority_from_impact(impact)
        items.append(
            {
                "category": category,
                "title": title,
                "tickers": tickers,
                "impact": impact,
                "priority": priority,
                "confidence": _confidence(impact),
                "action": ACTION_MAP.get(category, "Sledovat další potvrzení a price action."),
                "risk_note": RISK_MAP.get(category, "Riziko šumu bez obchodovatelného follow-through."),
                "status": _status_from(category, impact, priority),
                "timeframe": _timeframe_from(category),
                "bias": _bias_from(category, impact),
            }
        )
    return items


def render_briefing_message(
    briefing_text: str,
    items: List[Dict],
    decision: Dict | None = None,
    critic_summary: Dict | None = None,
    tracker_summary: Dict | None = None,
) -> str:
    if not items:
        return briefing_text.strip() or "Briefing zatím není."

    counts: Dict[str, int] = {}
    for item in items:
        counts[item["category"].upper()] = counts.get(item["category"].upper(), 0) + 1
    header_counts = " | ".join(f"{k}: {v}" for k, v in counts.items())

    lines = [
        "🧠 Live Intelligence Briefing",
        header_counts,
        "",
    ]
    if decision:
        lines.extend(
            [
                f"Režim dne: {decision.get('recommended_mode', 'NORMAL')}",
                f"Max nové pozice: {decision.get('max_new_positions', 0)}",
                f"Portfolio note: {decision.get('portfolio_note', 'Bez poznámky')}",
                "",
            ]
        )
    if critic_summary:
        lines.extend(
            [
                f"Critic: approved {critic_summary.get('approved_count', 0)} / rejected {critic_summary.get('rejected_count', 0)}",
                "",
            ]
        )
    if tracker_summary:
        lines.extend(
            [
                f"Tracker: records {tracker_summary.get('records', 0)} | pending {tracker_summary.get('pending_records', 0)} | scored {tracker_summary.get('scored_records', 0)}",
                "",
            ]
        )

    for idx, item in enumerate(items, start=1):
        tick = "🔴" if item["priority"] == "HIGH" else "🟡" if item["priority"] == "MEDIUM" else "🟢"
        lines.extend(
            [
                f"{idx}) {tick} {item['category'].upper()} | {item['priority']}",
                item["title"],
                f"Status: {item['status']} | Timeframe: {item['timeframe']}",
                f"Bias: {item['bias']}",
                f"Confidence: {item['confidence']:.2f} | Impact: {item['impact']:.3f}",
                f"Akce: {item['action']}",
                f"Riziko: {item['risk_note']}",
                "",
            ]
        )

    return "\n".join(lines).strip()[:4096]


def render_alerts_message(
    alerts: List[Dict],
    critic_summary: Dict | None = None,
    tracker_summary: Dict | None = None,
) -> str:
    if not alerts:
        return "Žádné alerty."

    lines = ["🚨 XTB Live Alerts", ""]
    if critic_summary:
        lines.extend(
            [
                f"Critic summary: approved {critic_summary.get('approved_count', 0)} | rejected {critic_summary.get('rejected_count', 0)}",
                "",
            ]
        )
    if tracker_summary:
        lines.extend(
            [
                f"Tracker: total {tracker_summary.get('records', 0)} | scored {tracker_summary.get('scored_records', 0)} | hit rate {tracker_summary.get('overall_hit_rate', 0.0):.2f}",
                "",
            ]
        )
    for idx, item in enumerate(alerts, start=1):
        tick = "🔴" if item["priority"] == "HIGH" else "🟡" if item["priority"] == "MEDIUM" else "🟢"
        tickers = ", ".join(item.get("tickers", [])) or "N/A"
        lines.extend(
            [
                f"{idx}) {tick} {item['category'].upper()} | {item['priority']}",
                item["title"],
                f"Tickery: {tickers}",
                f"Status: {item['status']} | Timeframe: {item['timeframe']}",
                f"Bias: {item['bias']}",
                f"Confidence: {item['confidence']:.2f} | Impact: {item['impact']:.3f}",
                f"Akce: {item['action']}",
                f"Riziko: {item['risk_note']}",
                "",
            ]
        )

    return "\n".join(lines).strip()[:4096]
