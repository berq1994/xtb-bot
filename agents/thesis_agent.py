from __future__ import annotations

import json
from pathlib import Path

STATE_PATH = Path("data/research_live_state.json")
JSON_PATH = Path("data/thesis_updates.json")
TEXT_PATH = Path("thesis_updates.txt")


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _strength_label(priority_score: float) -> str:
    if priority_score >= 3.2:
        return "silná"
    if priority_score >= 2.2:
        return "střední"
    return "slabší"


def _horizon(category: str) -> str:
    if category in {"portfolio_priority", "risk_watch"}:
        return "1-5 dní"
    if category in {"breakout_watch", "pullback_watch"}:
        return "1-3 dny"
    return "1-10 dní"


def _action(item: dict) -> str:
    category = item.get("category", "watchlist_monitor")
    trend = item.get("trend", "flat")
    sentiment = item.get("sentiment_label", "neutral")
    if category == "portfolio_priority" and sentiment == "negative":
        return "držet opatrně / nehonit růst"
    if category == "portfolio_priority" and trend == "up":
        return "držet / přikoupit jen na pullbacku"
    if category == "pullback_watch":
        return "sledovat pullback buy"
    if category == "breakout_watch":
        return "sledovat breakout buy"
    if category == "risk_watch":
        return "omezit riziko / počkat"
    return "watchlist bez akce"


def run_thesis_update() -> str:
    state = _load_state()
    top_items = state.get("top_items", []) if isinstance(state, dict) else []
    if not top_items:
        output = "THESIS UPDATE\nChybí data z research_live_state.json"
        TEXT_PATH.write_text(output, encoding="utf-8")
        return output

    updates = []
    for item in top_items[:8]:
        priority_score = float(item.get("priority_score", 0.0))
        sentiment = str(item.get("sentiment_label", "neutral"))
        trend = str(item.get("trend", "flat"))
        symbol = str(item.get("symbol", ""))
        held = bool(item.get("held", False))

        if sentiment == "negative":
            thesis_change = "oslabení teze"
        elif trend == "up" and priority_score >= 2.4:
            thesis_change = "posílení teze"
        elif trend == "down" and held:
            thesis_change = "nutná kontrola teze"
        else:
            thesis_change = "beze změny"

        bull_case = "trend a sentiment zatím podporují pokračování"
        bear_case = "negativní zprávy nebo slabší follow-through mohou setup zlomit"
        if sentiment == "negative":
            bull_case = "pokles může nabídnout lepší cenu jen po stabilizaci"
            bear_case = "zprávy zhoršují pravděpodobnost rychlého obratu"
        elif trend == "flat":
            bull_case = "akcie může jen konsolidovat před dalším pohybem"
            bear_case = "bez impulsu může kapitál zůstat zamčený"

        updates.append(
            {
                "symbol": symbol,
                "thesis_change": thesis_change,
                "strength": _strength_label(priority_score),
                "confidence": min(5, max(1, int(round(priority_score + 1)))),
                "action": _action(item),
                "held": held,
                "time_horizon": _horizon(str(item.get("category", ""))),
                "bull_case": bull_case,
                "bear_case": bear_case,
                "category": item.get("category", "watchlist_monitor"),
                "priority_score": round(priority_score, 2),
            }
        )

    payload = {
        "regime": state.get("regime", "mixed"),
        "source": state.get("source", "unknown"),
        "updates": updates,
    }
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("THESIS UPDATE")
    lines.append(f"Režim trhu: {payload['regime']}")
    lines.append("")
    for item in updates:
        holding = "ano" if item["held"] else "ne"
        lines.append(
            f"- {item['symbol']} | {item['thesis_change']} | síla {item['strength']} | confidence {item['confidence']}/5 | akce {item['action']} | držená pozice {holding} | horizont {item['time_horizon']}"
        )
        lines.append(f"  bull: {item['bull_case']}")
        lines.append(f"  bear: {item['bear_case']}")
    output = "\n".join(lines).strip()
    TEXT_PATH.write_text(output, encoding="utf-8")
    return output
